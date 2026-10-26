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
    RedesInternas,
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

    def test_familia_que_no_coincide_con_la_regla_de_sobre(self):
        r = ejecutar(propuesta(familia_candidata="F3"))
        self.assertRechazo(r, MotivoRechazo.FAMILIA_NO_COINCIDE)
        self.assertIn("F3", r.detalle)
        self.assertIsInstance(ejecutar(propuesta(familia_candidata="F1")), Aprobada)

    def test_exclusion_con_varios_valores_por_categoria(self):
        r = ejecutar(propuesta(objetivo={"equipo": ["pc-ventas-12", "srv-bd-02"]}))
        self.assertRechazo(r, MotivoRechazo.ACTIVO_EXCLUIDO)

    def test_motivos_coinciden_con_el_esquema_de_tickets(self):
        # FAMILIA_NO_COINCIDE es nuevo y todavía falta en tickets.rechazo_motivo.
        self.assertEqual(
            {m.value for m in MotivoRechazo} - {"FAMILIA_NO_COINCIDE"},
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


class ExclusionDeIp(unittest.TestCase):
    """EXECUTE interpreta las IP con ipaddress; la exclusión debe verlas igual."""

    def test_formas_equivalentes_de_la_misma_ip_ipv4(self):
        exclusion = ListaExclusion.desde([("ip", "192.0.2.5")])
        for forma in (
            "192.0.2.5",
            "::ffff:192.0.2.5",
            "0:0:0:0:0:ffff:c000:205",
            "::FFFF:C000:205",
        ):
            with self.subTest(forma):
                self.assertEqual(
                    exclusion.coincidencia({"ip": [forma]}), ("ip", "192.0.2.5")
                )

    def test_formas_equivalentes_de_una_ip_ipv6(self):
        exclusion = ListaExclusion.desde([("ip", "2001:DB8::1")])
        for forma in ("2001:db8::1", "2001:0db8:0000:0000:0000:0000:0000:0001"):
            with self.subTest(forma):
                self.assertIsNotNone(exclusion.coincidencia({"ip": [forma]}))

    def test_la_entrada_tambien_puede_venir_en_otra_forma(self):
        exclusion = ListaExclusion.desde([("ip", "::ffff:192.0.2.5")])
        self.assertIsNotNone(exclusion.coincidencia({"ip": ["192.0.2.5"]}))

    def test_otra_ip_no_coincide(self):
        exclusion = ListaExclusion.desde([("ip", "192.0.2.5")])
        self.assertIsNone(
            exclusion.coincidencia({"ip": ["192.0.2.6", "::ffff:192.0.2.6"]})
        )

    def test_valor_que_no_es_ip_se_compara_como_texto(self):
        exclusion = ListaExclusion.desde([("ip", "no-es-una-ip")])
        self.assertIsNotNone(exclusion.coincidencia({"ip": ["NO-ES-UNA-IP"]}))

    def test_la_normalizacion_es_solo_de_la_categoria_ip(self):
        exclusion = ListaExclusion.desde([("equipo", "192.0.2.5")])
        self.assertIsNone(exclusion.coincidencia({"equipo": ["::ffff:192.0.2.5"]}))


REDES = RedesInternas.desde(["10.0.0.0/8", "192.168.0.0/16", "fc00::/7"])
BLOQUEO_EXTERNO = Playbook("PB-F1-02", "F1", 1, ambito_ip="externa")
BLOQUEO_INTERNO = Playbook("PB-F1-03", "F1", 2, ambito_ip="interna")


class AmbitoDeLaIp(unittest.TestCase):
    def veredicto(self, playbook, ip, redes=REDES):
        return validar(
            propuesta(playbook_id=playbook.id, ip_origen=ip),
            Catalogo.desde([playbook]),
            EXCLUSION,
            MAPA,
            ESTADO_OK,
            redes,
        )

    def test_es_interna(self):
        casos = {
            "10.1.2.3": True,
            "192.168.1.5": True,
            "::ffff:10.1.2.3": True,
            "fd00::1": True,
            "203.0.113.9": False,
            "::ffff:203.0.113.9": False,
            "2001:db8::1": False,
            "no-es-ip": None,
        }
        for ip, esperado in casos.items():
            with self.subTest(ip):
                self.assertIs(REDES.es_interna(ip), esperado)

    def test_bloqueo_externo_con_ip_externa_pasa(self):
        self.assertEqual(
            self.veredicto(BLOQUEO_EXTERNO, "203.0.113.9"), Aprobada("PB-F1-02", 1)
        )

    def test_bloqueo_externo_con_ip_interna_se_rechaza(self):
        for ip in ("10.1.2.3", "::ffff:10.1.2.3"):
            r = self.veredicto(BLOQUEO_EXTERNO, ip)
            self.assertIsInstance(r, Rechazo, ip)
            self.assertEqual(r.motivo, MotivoRechazo.PLAYBOOK_FUERA_DE_CATALOGO)
            self.assertIn("externa", r.detalle)

    def test_bloqueo_interno_con_ip_externa_se_rechaza(self):
        r = self.veredicto(BLOQUEO_INTERNO, "203.0.113.9")
        self.assertEqual(r.motivo, MotivoRechazo.PLAYBOOK_FUERA_DE_CATALOGO)
        self.assertEqual(
            self.veredicto(BLOQUEO_INTERNO, "10.1.2.3"), Aprobada("PB-F1-03", 2)
        )

    def test_sin_ip_valida_o_sin_redes_se_rechaza(self):
        for ip, redes in ((None, REDES), ("no-es-ip", REDES), ("203.0.113.9", None)):
            with self.subTest(ip=ip, redes=redes):
                r = self.veredicto(BLOQUEO_EXTERNO, ip, redes)
                self.assertEqual(r.motivo, MotivoRechazo.PLAYBOOK_FUERA_DE_CATALOGO)

    def test_un_playbook_sin_ambito_no_mira_la_ip(self):
        r = validar(
            propuesta(ip_origen=None), CATALOGO, EXCLUSION, MAPA, ESTADO_OK, None
        )
        self.assertIsInstance(r, Aprobada)

    def test_ambito_desconocido(self):
        with self.assertRaises(ValueError):
            Playbook("PB-F1-02", "F1", 1, ambito_ip="remota")


if __name__ == "__main__":
    unittest.main()
