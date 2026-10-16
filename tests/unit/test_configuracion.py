import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from validacion.catalogo import cargar_catalogo
from validacion.chequeos import Aprobada, MotivoRechazo, Propuesta, Rechazo, validar
from validacion.configuracion import (
    RUTA_CONFIGURACION,
    ConfiguracionInvalida,
    cargar_configuracion,
)

ORIGINAL = json.loads(RUTA_CONFIGURACION.read_text(encoding="utf-8"))
REGLAS_SOBRE = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "wazuh"
    / "reglas"
    / "kronos_reglas_sobre.xml"
)


class ConfiguracionPropuesta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conf = cargar_configuracion()

    def test_es_una_propuesta(self):
        self.assertEqual(ORIGINAL["estado"], "propuesta")

    def test_mapa_de_severidad(self):
        mapa = self.conf.mapa
        self.assertEqual(
            [mapa.nivel_maximo(s) for s in (0, 6, 7, 9, 10, 11, 12, 15)],
            [0, 0, 1, 1, 2, 2, 3, 3],
        )

    def test_cinco_contadores(self):
        self.assertEqual(len(self.conf.contadores) + 1, 5)
        self.assertEqual(self.conf.disparo_cortacircuito.tope, 30)
        self.assertEqual(self.conf.disparo_cortacircuito.ventana_minutos, 10)

    def test_cortacircuito_se_abre_con_30_alertas(self):
        self.assertFalse(self.conf.debe_abrir_cortacircuito(29))
        self.assertTrue(self.conf.debe_abrir_cortacircuito(30))

    def test_contador_sin_dato_cuenta_como_en_su_tope(self):
        estado = self.conf.estado_operacion({"acciones_por_inquilino": 2}, False)
        usados = {c.nombre: (c.usados, c.tope) for c in estado.contadores}
        self.assertEqual(usados["acciones_por_inquilino"], (2, 10))
        self.assertEqual(usados["acciones_por_equipo"], (3, 3))

    def test_niveles_que_permite_cada_regla_de_sobre(self):
        # Las 15 reglas de sobre (infra/wazuh) tienen niveles 7, 8, 10 y 12.
        niveles = {
            int(n)
            for n in re.findall(
                r'<rule id="1001\d\d" level="(\d+)"', REGLAS_SOBRE.read_text()
            )
        }
        self.assertEqual(niveles, {7, 8, 10, 12})
        self.assertEqual(
            {n: self.conf.mapa.nivel_maximo(n) for n in sorted(niveles)},
            {7: 1, 8: 1, 10: 2, 12: 3},
        )

    def test_de_punta_a_punta_con_el_catalogo(self):
        catalogo = cargar_catalogo()
        usos = {c.nombre: 0 for c in self.conf.contadores}
        estado = self.conf.estado_operacion(usos, cortacircuito_abierto=False)

        def resultado(playbook, severidad):
            familia = playbook[3:5]
            return validar(
                Propuesta(
                    familia,
                    playbook,
                    0.9,
                    severidad,
                    {"equipo": "pc-ventas-12"},
                    ip_origen="203.0.113.9",
                ),
                catalogo,
                self.conf.exclusion,
                self.conf.mapa,
                estado,
                self.conf.redes_internas,
            )

        # Fuerza bruta (regla 100101, nivel 10): bloquear la IP (nivel 1) sí; aislar (nivel 3) no.
        self.assertEqual(resultado("PB-F1-02", 10), Aprobada("PB-F1-02", 1))
        r = resultado("PB-F3-03", 10)
        self.assertIsInstance(r, Rechazo)
        self.assertEqual(r.motivo, MotivoRechazo.NIVEL_NO_PERMITIDO_POR_SEVERIDAD)
        # Disco lleno (regla 100114, nivel 7): detener un servicio (nivel 3) no.
        self.assertEqual(
            resultado("PB-F6-04", 7).motivo,
            MotivoRechazo.NIVEL_NO_PERMITIDO_POR_SEVERIDAD,
        )


class ConfiguracionDefectuosa(unittest.TestCase):
    def cargar_con(self, cambiar):
        datos = copy.deepcopy(ORIGINAL)
        cambiar(datos)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "validate.json"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            return cargar_configuracion(ruta)

    def test_exclusion_cargada(self):
        conf = self.cargar_con(
            lambda d: d["exclusion"]["entradas"].append(
                {"categoria": "equipo", "valor": "srv-bd-02"}
            )
        )
        self.assertIsNotNone(conf.exclusion.coincidencia({"equipo": "SRV-BD-02"}))

    def test_rechazos(self):
        casos = {
            "otro código": lambda d: d.update(codigo="X"),
            "mapa con hueco": lambda d: d["mapa_severidad"].pop(1),
            "nivel decreciente": lambda d: d["mapa_severidad"][3].update(
                nivel_maximo=1
            ),
            "nivel como texto": lambda d: d["mapa_severidad"][0].update(
                nivel_maximo="0"
            ),
            "categoría de exclusión de menos": lambda d: d["exclusion"][
                "categorias"
            ].pop("ip"),
            "entrada con categoría desconocida": lambda d: d["exclusion"][
                "entradas"
            ].append({"categoria": "usuario", "valor": "x"}),
            "entrada vacía": lambda d: d["exclusion"]["entradas"].append(
                {"categoria": "equipo", "valor": "  "}
            ),
            "contador repetido": lambda d: d["contadores"].append(d["contadores"][0]),
            "tope cero": lambda d: d["contadores"][0].update(tope=0),
            "tope booleano": lambda d: d["contadores"][0].update(tope=True),
            "sin redes internas": lambda d: d.pop("redes_internas"),
            "redes internas vacías": lambda d: d.update(redes_internas=[]),
            "red interna mal escrita": lambda d: d.update(
                redes_internas=["10.0.0.0/33"]
            ),
            "red interna con bits de host": lambda d: d.update(
                redes_internas=["10.0.0.1/8"]
            ),
            "red interna que no es texto": lambda d: d.update(redes_internas=[10]),
            "sin disparo del cortacircuito": lambda d: d.pop("disparo_cortacircuito"),
        }
        for nombre, cambiar in casos.items():
            with self.subTest(nombre), self.assertRaises(ConfiguracionInvalida):
                self.cargar_con(cambiar)


if __name__ == "__main__":
    unittest.main()
