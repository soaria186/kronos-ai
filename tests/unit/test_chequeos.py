import math
import unittest

from validacion.chequeos import (
    Aprobada,
    Catalogo,
    Contador,
    EstadoOperacion,
    ListaExclusion,
    MapaSeveridad,
    MotivoRechazo,
    Playbook,
    Propuesta,
    Rechazo,
    validar,
)

# Valores de EJEMPLO para las pruebas; no son decisiones del equipo.
CATALOGO = Catalogo.desde(
    [
        Playbook("PB-F1-01", "F1", 0),
        Playbook("PB-F1-02", "F1", 1),
        Playbook("PB-F1-05", "F1", 2),
        Playbook("PB-F3-03", "F3", 3),
    ]
)
EXCLUSION = ListaExclusion.desde([("equipo", "srv-bd-02"), ("cuenta", "svc_respaldo")])
MAPA = MapaSeveridad(((0, 4, 0), (5, 9, 1), (10, 11, 2), (12, 15, 3)))
ESTADO_OK = EstadoOperacion(
    cortacircuito_abierto=False,
    contadores=(Contador("acciones por hora", 3, 10), Contador("por equipo", 0, 2)),
)


def propuesta(**cambios):
    base = {
        "familia": "F1",
        "playbook_id": "PB-F1-02",
        "confianza": 0.85,
        "severidad": 10,
        "objetivo": {"equipo": "pc-ventas-12", "ip": "192.0.2.77"},
    }
    base.update(cambios)
    return Propuesta(**base)


def ejecutar(p, estado=ESTADO_OK):
    return validar(p, CATALOGO, EXCLUSION, MAPA, estado)


class Validar(unittest.TestCase):
    def assertRechazo(self, resultado, motivo):
        self.assertIsInstance(resultado, Rechazo)
        self.assertEqual(resultado.motivo, motivo)

    def test_aprobada_devuelve_el_nivel_del_catalogo(self):
        self.assertEqual(ejecutar(propuesta()), Aprobada("PB-F1-02", 1))

    def test_confianza_justo_en_el_umbral_pasa(self):
        self.assertIsInstance(ejecutar(propuesta(confianza=0.70)), Aprobada)

    def test_confianza_bajo_el_umbral(self):
        self.assertRechazo(
            ejecutar(propuesta(confianza=0.69)), MotivoRechazo.CONFIANZA_BAJA
        )

    def test_confianza_nan(self):
        self.assertRechazo(
            ejecutar(propuesta(confianza=math.nan)), MotivoRechazo.CONFIANZA_BAJA
        )

    def test_playbook_inexistente(self):
        self.assertRechazo(
            ejecutar(propuesta(playbook_id="PB-F1-99")),
            MotivoRechazo.PLAYBOOK_FUERA_DE_CATALOGO,
        )

    def test_playbook_de_otra_familia(self):
        self.assertRechazo(
            ejecutar(propuesta(playbook_id="PB-F3-03")),
            MotivoRechazo.PLAYBOOK_FUERA_DE_CATALOGO,
        )

    def test_objetivo_excluido_sin_importar_mayusculas(self):
        r = ejecutar(propuesta(objetivo={"Equipo": " SRV-BD-02 "}))
        self.assertRechazo(r, MotivoRechazo.ACTIVO_EXCLUIDO)
        self.assertIn("srv-bd-02", r.detalle)

    def test_exclusion_es_por_categoria(self):
        # svc_respaldo está excluida como cuenta, no como equipo.
        self.assertIsInstance(
            ejecutar(propuesta(objetivo={"equipo": "svc_respaldo"})), Aprobada
        )

    def test_cortacircuito_abierto(self):
        estado = EstadoOperacion(cortacircuito_abierto=True)
        self.assertRechazo(
            ejecutar(propuesta(), estado), MotivoRechazo.CORTACIRCUITO_ABIERTO
        )

    def test_contador_en_su_tope(self):
        estado = EstadoOperacion(False, (Contador("acciones por hora", 10, 10),))
        r = ejecutar(propuesta(), estado)
        self.assertRechazo(r, MotivoRechazo.LIMITE_DE_TASA)
        self.assertIn("acciones por hora", r.detalle)

    def test_nivel_no_permitido_por_severidad(self):
        self.assertRechazo(
            ejecutar(propuesta(severidad=3)),
            MotivoRechazo.NIVEL_NO_PERMITIDO_POR_SEVERIDAD,
        )

    def test_severidad_baja_permite_nivel_0(self):
        self.assertEqual(
            ejecutar(propuesta(playbook_id="PB-F1-01", severidad=3)),
            Aprobada("PB-F1-01", 0),
        )

    def test_orden_de_los_chequeos(self):
        # Falla todo a la vez: gana el primero de la lista (confianza).
        todo_mal = propuesta(
            confianza=0.1,
            playbook_id="PB-F3-03",
            objetivo={"equipo": "srv-bd-02"},
            severidad=0,
        )
        estado = EstadoOperacion(True, (Contador("x", 9, 1),))
        self.assertRechazo(ejecutar(todo_mal, estado), MotivoRechazo.CONFIANZA_BAJA)
        # Sin el problema de confianza, gana el catálogo; y así sucesivamente.
        self.assertRechazo(
            ejecutar(
                propuesta(playbook_id="PB-F3-03", objetivo={"equipo": "srv-bd-02"}),
                estado,
            ),
            MotivoRechazo.PLAYBOOK_FUERA_DE_CATALOGO,
        )
        self.assertRechazo(
            ejecutar(propuesta(objetivo={"equipo": "srv-bd-02"}), estado),
            MotivoRechazo.ACTIVO_EXCLUIDO,
        )
        self.assertRechazo(
            ejecutar(propuesta(), estado), MotivoRechazo.CORTACIRCUITO_ABIERTO
        )

    def test_motivos_coinciden_con_el_esquema_de_tickets(self):
        self.assertEqual(
            {m.value for m in MotivoRechazo},
            {
                "CONFIANZA_BAJA",
                "PLAYBOOK_FUERA_DE_CATALOGO",
                "ACTIVO_EXCLUIDO",
                "CORTACIRCUITO_ABIERTO",
                "LIMITE_DE_TASA",
                "NIVEL_NO_PERMITIDO_POR_SEVERIDAD",
            },
        )


class DatosDeConfiguracion(unittest.TestCase):
    def test_mapa_con_hueco(self):
        with self.assertRaises(ValueError):
            MapaSeveridad(((0, 4, 0), (6, 15, 1)))

    def test_mapa_incompleto(self):
        with self.assertRaises(ValueError):
            MapaSeveridad(((0, 9, 0),))

    def test_mapa_con_nivel_decreciente(self):
        with self.assertRaises(ValueError):
            MapaSeveridad(((0, 9, 2), (10, 15, 1)))

    def test_severidad_fuera_de_rango(self):
        with self.assertRaises(ValueError):
            MAPA.nivel_maximo(16)

    def test_playbook_con_nivel_invalido(self):
        with self.assertRaises(ValueError):
            Playbook("PB-F1-09", "F1", 4)

    def test_catalogo_con_repetidos(self):
        with self.assertRaises(ValueError):
            Catalogo.desde(
                [Playbook("PB-F1-01", "F1", 0), Playbook("PB-F1-01", "F1", 1)]
            )


if __name__ == "__main__":
    unittest.main()
