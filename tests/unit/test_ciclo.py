import copy
import json
import tempfile
import unittest
from collections import namedtuple
from dataclasses import dataclass, replace
from pathlib import Path

from conectores.alertas_wazuh import Posicion
from decision.inferencia import MotorNoDisponible
from decision.plantillas import Plantillas
from validacion import posicion
from validacion.alerta import preparar
from validacion.catalogo import cargar_catalogo
from validacion.chequeos import Catalogo, ListaExclusion, Playbook
from validacion.ciclo import (
    Destino,
    PromptDistintoDelCatalogo,
    Validador,
    comprobar_prompt,
    equipo_de,
    es_manager,
)
from validacion.configuracion import cargar_configuracion

ALERTAS_150 = (
    Path(__file__).resolve().parents[2]
    / "decision"
    / "mediciones"
    / "casos_150"
    / "alertas.json"
)

PLANTILLAS = Plantillas.cargar()
CONFIG = cargar_configuracion()
NIVEL = {"PB-F1-01": 2, "PB-F1-02": 1, "PB-F2-02": 1, "PB-F3-03": 3}

Ticket = namedtuple("Ticket", "ticket_id nuevo")


@dataclass(frozen=True)
class DecisionFalsa:
    familia: str | None
    playbook_id: str | None
    confianza: float | None
    nivel: int | None
    motivo: str | None = None
    detalle: str = ""
    equipo: str | None = None


def catalogo_del_prompt():
    """Catálogo cuyas medidas son las que el prompt le describe al modelo."""
    return Catalogo.desde(
        [
            Playbook(i, f, NIVEL.get(i, 0), datos.nombres[i])
            for f, datos in PLANTILLAS.familias.items()
            for i in datos.candidatos
        ]
    )


class AlmacenFalso:
    def __init__(self, nuevo=True, alertas=1, abierto=False, usos=None):
        self.nuevo = nuevo
        self.alertas = alertas
        self.abierto = abierto
        self.usos_dev = (
            {c.nombre: 0 for c in CONFIG.contadores} if usos is None else usos
        )
        self.registradas = []
        self.decisiones = []
        self.consultas_usos = []
        self.aperturas = []

    def registrar_alerta(self, tenant_id, alerta_ref, titulo, severidad, detalle=None):
        self.registradas.append(alerta_ref)
        return Ticket(len(self.registradas), self.nuevo)

    def registrar_decision(self, tenant_id, ticket_id, decision):
        self.decisiones.append((tenant_id, ticket_id, decision))
        return len(self.decisiones)

    def usos(self, tenant_id, definiciones, equipo=None, playbook_id=None):
        self.consultas_usos.append((equipo, playbook_id))
        return dict(self.usos_dev)

    def alertas_en_ventana(self, tenant_id, ventana_minutos):
        return self.alertas

    def cortacircuito_abierto(self, tenant_id):
        return self.abierto

    def abrir_cortacircuito(self, tenant_id, motivo):
        self.aperturas.append(motivo)
        self.abierto = True
        return True


class ModeloFalso:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = 0

    def generar(self, prompt, esquema, plazo):
        self.llamadas += 1
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def acierta(familia="F1", playbook="PB-F1-02", c1=0.9, c2=0.85):
    return ModeloFalso(
        json.dumps({"familia": familia, "confianza": c1}),
        json.dumps({"playbook_id": playbook, "confianza": c2}),
    )


def alerta_ssh():
    """K150-001: fuerza bruta por SSH (regla 100101, F1, nivel 10) en srv-web-01."""
    return copy.deepcopy(json.loads(ALERTAS_150.read_text())[0]["alerta"])


def validador(almacen, modelo, configuracion=CONFIG):
    return Validador(
        almacen,
        modelo,
        PLANTILLAS,
        catalogo_del_prompt(),
        configuracion,
        DecisionFalsa,
    )


class Ciclo(unittest.TestCase):
    def test_aprobada_registra_la_decision_con_el_equipo_normalizado(self):
        almacen, modelo = AlmacenFalso(), acierta()
        alerta = alerta_ssh()
        alerta["agent"]["name"] = "  SRV-Web-01 "
        r = validador(almacen, modelo).procesar(1, alerta)

        self.assertEqual(r.destino, Destino.APROBADA)
        ((_, ticket_id, d),) = almacen.decisiones
        self.assertEqual(ticket_id, r.ticket_id)
        self.assertEqual(
            (d.familia, d.playbook_id, d.nivel, d.motivo, d.equipo),
            ("F1", "PB-F1-02", 1, None, "srv-web-01"),
        )
        self.assertEqual(d.confianza, 0.85)  # la menor de los dos pasos
        # El contador por equipo se consulta con el mismo valor que se guarda.
        self.assertEqual(almacen.consultas_usos, [("srv-web-01", "PB-F1-02")])

    def test_no_kronos_se_omite_sin_tocar_nada(self):
        almacen, modelo = AlmacenFalso(), acierta()
        alerta = alerta_ssh()
        alerta["rule"]["groups"] = ["syslog", "sshd"]
        self.assertEqual(
            validador(almacen, modelo).procesar(1, alerta).destino, Destino.OMITIDA
        )
        self.assertEqual(
            (almacen.registradas, almacen.decisiones, modelo.llamadas), ([], [], 0)
        )

    def test_alerta_invalida_se_descarta_sin_tocar_la_base(self):
        almacen, modelo = AlmacenFalso(), acierta()
        alerta = alerta_ssh()
        alerta["rule"]["level"] = "alto"
        r = validador(almacen, modelo).procesar(1, alerta)
        self.assertEqual(r.destino, Destino.DESCARTADA)
        self.assertEqual(
            (almacen.registradas, almacen.decisiones, modelo.llamadas), ([], [], 0)
        )

    def test_alerta_repetida_no_se_vuelve_a_procesar(self):
        almacen, modelo = AlmacenFalso(nuevo=False), acierta()
        r = validador(almacen, modelo).procesar(1, alerta_ssh())
        self.assertEqual(r.destino, Destino.REPETIDA)
        self.assertEqual((almacen.decisiones, modelo.llamadas), ([], 0))

    # ---------------------------------------------------------------- rechazos

    def rechazada(self, almacen, modelo, motivo, alerta=None, configuracion=CONFIG):
        r = validador(almacen, modelo, configuracion).procesar(
            1, alerta or alerta_ssh()
        )
        self.assertEqual((r.destino, r.motivo), (Destino.RECHAZADA, motivo))
        ((_, _, d),) = almacen.decisiones
        self.assertEqual((d.motivo, d.nivel), (motivo, None))
        return d

    def test_la_familia_del_modelo_debe_coincidir_con_la_regla_de_sobre(self):
        d = self.rechazada(
            AlmacenFalso(), acierta("F2", "PB-F2-02"), "FAMILIA_NO_COINCIDE"
        )
        self.assertEqual((d.familia, d.playbook_id), ("F2", "PB-F2-02"))

    def test_confianza_baja(self):
        self.rechazada(AlmacenFalso(), acierta(c1=0.9, c2=0.5), "CONFIANZA_BAJA")

    def test_falla_del_modelo_va_a_revision_humana(self):
        modelo = ModeloFalso(MotorNoDisponible("apagado"))
        almacen = AlmacenFalso()
        d = self.rechazada(almacen, modelo, "MOTOR_INFERENCIA_NO_DISPONIBLE")
        self.assertIn("paso 1", d.detalle)
        self.assertEqual(almacen.consultas_usos, [])

    def test_respuesta_fuera_de_contrato(self):
        modelo = ModeloFalso("esto no es json")
        self.rechazada(AlmacenFalso(), modelo, "ESQUEMA_INVALIDO")

    def test_equipo_excluido_aunque_cambie_la_escritura(self):
        config = replace(
            CONFIG, exclusion=ListaExclusion.desde([("equipo", "SRV-WEB-01")])
        )
        alerta = alerta_ssh()
        alerta["agent"]["name"] = " srv-Web-01"
        self.rechazada(AlmacenFalso(), acierta(), "ACTIVO_EXCLUIDO", alerta, config)

    def test_ip_excluida_aunque_se_escriba_distinto(self):
        config = replace(CONFIG, exclusion=ListaExclusion.desde([("ip", "192.0.2.77")]))
        alerta = alerta_ssh()
        alerta["data"]["srcip"] = "::ffff:192.0.2.77"
        self.rechazada(AlmacenFalso(), acierta(), "ACTIVO_EXCLUIDO", alerta, config)

    def test_contador_en_su_tope(self):
        usos = {c.nombre: 0 for c in CONFIG.contadores} | {"acciones_por_equipo": 3}
        d = self.rechazada(AlmacenFalso(usos=usos), acierta(), "LIMITE_DE_TASA")
        self.assertIn("acciones_por_equipo", d.detalle)

    def test_sin_datos_de_contadores_no_se_automatiza(self):
        self.rechazada(AlmacenFalso(usos={}), acierta(), "LIMITE_DE_TASA")

    def test_alerta_sin_equipo_no_se_automatiza(self):
        # Sin nombre de equipo el contador por equipo no se puede consultar (falla segura).
        alerta = alerta_ssh()
        del alerta["agent"]["name"]
        self.assertIsNone(equipo_de(preparar(alerta)))
        almacen = AlmacenFalso(usos={c.nombre: 0 for c in CONFIG.contadores})
        almacen.usos = lambda *a, **k: {
            c.nombre: 0 for c in CONFIG.contadores if c.nombre != "acciones_por_equipo"
        }
        self.rechazada(almacen, acierta(), "LIMITE_DE_TASA", alerta)

    def test_severidad_limita_el_nivel(self):
        alerta = alerta_ssh()
        alerta["rule"]["level"] = 8  # nivel máximo 1
        modelo = acierta("F1", "PB-F1-01")  # nivel 2
        self.rechazada(
            AlmacenFalso(), modelo, "NIVEL_NO_PERMITIDO_POR_SEVERIDAD", alerta
        )

    def test_el_manager_nunca_se_toca_ni_se_consulta_al_modelo(self):
        for identificador in ("000", 0, " 0 "):
            alerta = alerta_ssh()
            alerta["agent"]["id"] = identificador
            almacen, modelo = AlmacenFalso(), acierta()
            self.rechazada(almacen, modelo, "ACTIVO_EXCLUIDO", alerta)
            self.assertEqual(modelo.llamadas, 0)

    def test_es_manager(self):
        self.assertTrue(es_manager({"agent": {"id": "000"}}))
        for alerta in (
            {"agent": {"id": "003"}},
            {"agent": {"id": None}},
            {"agent": {"id": False}},
            {"agent": "000"},
            {},
        ):
            self.assertFalse(es_manager(alerta), alerta)

    # ----------------------------------------------------------- cortacircuito

    def test_cortacircuito_abierto_rechaza_sin_llamar_al_modelo(self):
        almacen, modelo = AlmacenFalso(abierto=True), acierta()
        self.rechazada(almacen, modelo, "CORTACIRCUITO_ABIERTO")
        self.assertEqual((modelo.llamadas, almacen.aperturas), (0, []))

    def test_al_llegar_al_disparo_se_abre_y_se_rechaza(self):
        disparo = CONFIG.disparo_cortacircuito
        almacen, modelo = AlmacenFalso(alertas=disparo.tope), acierta()
        self.rechazada(almacen, modelo, "CORTACIRCUITO_ABIERTO")
        self.assertEqual(len(almacen.aperturas), 1)
        self.assertIn(str(disparo.tope), almacen.aperturas[0])
        self.assertEqual(modelo.llamadas, 0)

    def test_bajo_el_disparo_no_se_abre(self):
        almacen = AlmacenFalso(alertas=CONFIG.disparo_cortacircuito.tope - 1)
        self.assertEqual(
            validador(almacen, acierta()).procesar(1, alerta_ssh()).destino,
            Destino.APROBADA,
        )
        self.assertEqual(almacen.aperturas, [])

    # ------------------------------------------------------- las 150 alertas

    def test_las_150_alertas_pasan_el_ciclo_sin_error(self):
        casos = json.loads(ALERTAS_150.read_text())
        almacen = AlmacenFalso()
        resultados = []
        for caso in casos:
            familia = caso["familia_esperada"]
            primero = PLANTILLAS.familias[familia].candidatos[0]
            resultados.append(
                validador(almacen, acierta(familia, primero)).procesar(
                    1, caso["alerta"]
                )
            )
        self.assertEqual(len(almacen.decisiones), 150)
        self.assertEqual(len(set(almacen.registradas)), 150)
        self.assertTrue(
            all(r.destino in (Destino.APROBADA, Destino.RECHAZADA) for r in resultados)
        )
        for _, _, d in almacen.decisiones:
            if d.motivo is None:
                self.assertIsNotNone(d.nivel)


class PromptYCatalogo(unittest.TestCase):
    def test_el_prompt_describe_el_catalogo_real(self):
        comprobar_prompt(PLANTILLAS, cargar_catalogo())

    def test_un_prompt_con_otras_medidas_no_pasa(self):
        # Como el catálogo provisional de medición: mismos identificadores, otro significado.
        familias = {
            f: replace(d, nombres={i: "Bloqueo del origen" for i in d.candidatos})
            for f, d in PLANTILLAS.familias.items()
        }
        ajeno = replace(PLANTILLAS, familias=familias)
        with self.assertRaises(PromptDistintoDelCatalogo) as ctx:
            comprobar_prompt(ajeno, cargar_catalogo())
        self.assertIn("KRO-CAT-01", str(ctx.exception))
        with self.assertRaises(PromptDistintoDelCatalogo):
            Validador(
                AlmacenFalso(),
                acierta(),
                ajeno,
                cargar_catalogo(),
                CONFIG,
                DecisionFalsa,
            )

    def test_un_catalogo_de_prueba_con_las_mismas_medidas_pasa(self):
        comprobar_prompt(PLANTILLAS, catalogo_del_prompt())

    def test_un_candidato_que_no_esta_en_el_catalogo_falla(self):
        sin_uno = Catalogo.desde(
            [p for p in catalogo_del_prompt().playbooks.values() if p.id != "PB-F1-01"]
        )
        with self.assertRaises(PromptDistintoDelCatalogo):
            comprobar_prompt(PLANTILLAS, sin_uno)


class PosicionDeLectura(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.ruta = Path(self.dir.name) / "posicion.json"

    def test_se_guarda_y_se_recupera(self):
        posicion.guardar(self.ruta, Posicion(1234, 98765))
        self.assertEqual(posicion.cargar(self.ruta), Posicion(1234, 98765))
        self.assertEqual(
            [p.name for p in Path(self.dir.name).iterdir()], ["posicion.json"]
        )

    def test_sin_archivo_o_ilegible_no_hay_posicion(self):
        self.assertIsNone(posicion.cargar(self.ruta))
        for contenido in (
            "",
            "no es json",
            "[]",
            '{"inodo": 1}',
            '{"inodo": -1, "desplazamiento": 0}',
            '{"inodo": true, "desplazamiento": 0}',
            '{"inodo": "1", "desplazamiento": 0}',
        ):
            self.ruta.write_text(contenido)
            self.assertIsNone(posicion.cargar(self.ruta), contenido)


if __name__ == "__main__":
    unittest.main()
