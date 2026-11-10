"""EXECUTE con las acciones de D-69: cuarentena, bloquear_destino, limitar_conexiones y
revertir_tarea. Los valores que no calzan se rechazan, nunca se limpian."""

import unittest

from ejecucion.ordenes import (
    COMANDOS,
    ArgumentoFaltante,
    OrdenInvalida,
    construir,
    construir_reversion,
    leer_ip_protegidas,
)


def win(**eventdata):
    return {"agent": {"id": "002", "ip": "10.0.2.15"}, "data": {"win": {"eventdata": eventdata}}}


def linux(**campos):
    return {"agent": {"id": "001", "ip": "10.0.2.16"}, **campos}


class Comandos(unittest.TestCase):
    def test_los_cuatro_comandos_nuevos(self):
        self.assertEqual(COMANDOS["cuarentena"], ("kronos-cuarentena", "restaurar"))
        self.assertEqual(COMANDOS["bloquear_destino"], ("kronos-bloquear-destino", "quitar"))
        self.assertEqual(COMANDOS["limitar_conexiones"], ("kronos-limitar-conexiones", "quitar"))
        self.assertEqual(COMANDOS["revertir_tarea"], ("kronos-revertir-tarea", "habilitar"))

    def test_la_consulta_no_tiene_comando(self):
        self.assertNotIn("consulta", COMANDOS)


class Cuarentena(unittest.TestCase):
    def test_windows_desde_sysmon(self):
        ruta = "C:\\Users\\usuario01\\AppData\\Local\\Temp\\factura_0.exe"
        orden = construir("cuarentena", win(image=ruta), sistema="windows")
        self.assertEqual(orden.comando, "kronos-cuarentena")
        self.assertEqual(orden.argumentos, ("aplicar", ruta))
        reversion = construir_reversion("cuarentena", win(image=ruta), sistema="windows")
        self.assertEqual(reversion.argumentos, ("restaurar", ruta))

    def test_windows_con_espacios_parentesis_y_tildes(self):
        ruta = "D:\\Documentos (copia)\\Facturación 2026\\informe v2.exe"
        orden = construir("cuarentena", win(image=ruta), sistema="windows")
        self.assertEqual(orden.argumentos[1], ruta)

    def test_linux_desde_integridad_de_archivos(self):
        alerta = linux(syscheck={"path": "/home/labadmin/descargas/x.sh"})
        orden = construir("cuarentena", alerta, sistema="linux")
        self.assertEqual(orden.argumentos, ("aplicar", "/home/labadmin/descargas/x.sh"))

    def test_linux_desde_auditd(self):
        alerta = linux(data={"audit": {"exe": "/tmp/.x/minero"}})
        self.assertEqual(construir("cuarentena", alerta, sistema="linux").argumentos[1], "/tmp/.x/minero")

    def test_syscheck_manda_sobre_image(self):
        alerta = win(image="C:\\Users\\Public\\b.exe")
        alerta["syscheck"] = {"path": "C:\\Users\\Public\\a.exe"}
        self.assertEqual(construir("cuarentena", alerta, sistema="windows").argumentos[1], "C:\\Users\\Public\\a.exe")

    def test_sin_ruta_es_argumento_faltante(self):
        # E4 del 03-11: el borrado del registro de seguridad no trae archivo.
        with self.assertRaises(ArgumentoFaltante):
            construir("cuarentena", win(subjectUserName="usuario.demo"), sistema="windows")

    def test_rutas_de_windows_rechazadas(self):
        for ruta in (
            "C:\\Windows\\System32\\certutil.exe",  # carpeta del sistema
            "c:\\WINDOWS\\explorer.exe",
            "C:\\Program Files (x86)\\ossec-agent\\wazuh-agent.exe",  # agente
            "C:\\ProgramData\\Kronos\\cuarentena\\x.exe",  # la propia cuarentena
            "C:\\PROGRA~2\\ossec-agent\\x.exe",  # nombre corto
            "C:\\Users\\..\\Windows\\x.exe",
            "C:\\Users\\.\\x.exe",
            "C:\\Users\\x.exe:flujo",  # flujo alternativo
            "C:\\Users\\x.exe.",  # Windows recorta el punto final
            "C:\\Users\\x.exe ",
            "C:\\Users\\x$(whoami).exe",
            "C:\\Users\\a;b.exe",
            "C:\\Users\\a&b.exe",
            "C:\\Users\\a`b.exe",
            "C:\\Users\\a%TEMP%.exe",
            "C:\\Users\\*.exe",
            "C:/Users/x.exe",
            "\\\\servidor\\c$\\x.exe",
            "C:\\",
            "C:\\\\Users\\\\\\\\x.exe",  # separador doble, tal como lo entrega Wazuh
            "C:\\Users\\x.exe\nC:\\otro.exe",
            "/tmp/x",  # ruta de Linux en un agente Windows
            "C:\\" + "a" * 300 + ".exe",
        ):
            with self.subTest(ruta=ruta), self.assertRaises(OrdenInvalida):
                construir("cuarentena", win(image=ruta), sistema="windows")

    def test_rutas_de_linux_rechazadas(self):
        for ruta in (
            "/etc/sudoers",
            "/usr/bin/ls",
            "/bin/sh",
            "/var/ossec/bin/wazuh-agentd",
            "/var/lib/kronos/cuarentena/x",
            "/boot/vmlinuz",
            "/tmp/../etc/passwd",
            "/tmp/./x",
            "/tmp//x",
            "/tmp/x/",
            "/tmp/$(id)",
            "/tmp/a;b",
            "/tmp/~x",
            "tmp/x",
            "/",
            "C:\\Users\\x.exe",  # ruta de Windows en un agente Linux
        ):
            with self.subTest(ruta=ruta), self.assertRaises(OrdenInvalida):
                construir("cuarentena", linux(syscheck={"path": ruta}), sistema="linux")

    def test_valor_que_no_es_texto(self):
        with self.assertRaises(OrdenInvalida):
            construir("cuarentena", win(image=["C:\\a.exe"]), sistema="windows")


class BloquearDestino(unittest.TestCase):
    def test_sysmon(self):
        orden = construir("bloquear_destino", win(destinationIp="198.51.100.20"), sistema="windows")
        self.assertEqual(orden.comando, "kronos-bloquear-destino")
        self.assertEqual(orden.argumentos, ("aplicar", "198.51.100.20"))
        reversion = construir_reversion("bloquear_destino", win(destinationIp="198.51.100.20"), sistema="windows")
        self.assertEqual(reversion.argumentos, ("quitar", "198.51.100.20"))

    def test_linux(self):
        alerta = linux(data={"dstip": "203.0.113.80", "srcip": "10.0.2.16"})
        self.assertEqual(construir("bloquear_destino", alerta, sistema="linux").argumentos[1], "203.0.113.80")

    def test_no_usa_la_ip_de_origen(self):
        with self.assertRaises(ArgumentoFaltante):
            construir("bloquear_destino", linux(data={"srcip": "203.0.113.80"}), sistema="linux")

    def test_nunca_el_manager_ni_la_puerta_de_enlace(self):
        protegidas = leer_ip_protegidas("203.0.113.10, 10.0.50.1")
        for ip in ("203.0.113.10", "::ffff:203.0.113.10", "10.0.50.1"):
            with self.subTest(ip=ip), self.assertRaises(OrdenInvalida):
                construir("bloquear_destino", win(destinationIp=ip), sistema="windows", ip_protegidas=protegidas)

    def test_rechazos(self):
        for ip in ("127.0.0.1", "0.0.0.0", "224.0.0.1", "::ffff:127.0.0.1", "10.0.2.15", "1.2.3.4;id", "a"):
            with self.subTest(ip=ip), self.assertRaises(OrdenInvalida):
                construir("bloquear_destino", win(destinationIp=ip), sistema="windows")


class LimitarConexiones(unittest.TestCase):
    def test_usa_la_ip_de_origen(self):
        alerta = linux(data={"srcip": "198.51.100.9"})
        orden = construir("limitar_conexiones", alerta, sistema="linux")
        self.assertEqual(orden.comando, "kronos-limitar-conexiones")
        self.assertEqual(orden.argumentos, ("aplicar", "198.51.100.9"))
        self.assertEqual(construir_reversion("limitar_conexiones", alerta, sistema="linux").argumentos[0], "quitar")

    def test_ip_protegida(self):
        with self.assertRaises(OrdenInvalida):
            construir(
                "limitar_conexiones",
                linux(data={"srcip": "10.0.50.1"}),
                sistema="linux",
                ip_protegidas=leer_ip_protegidas("10.0.50.1"),
            )

    def test_bloquear_ip_tambien_respeta_las_protegidas(self):
        with self.assertRaises(OrdenInvalida):
            construir(
                "bloquear_ip",
                linux(data={"srcip": "203.0.113.10"}),
                sistema="linux",
                ip_protegidas=leer_ip_protegidas("203.0.113.10"),
            )


class RevertirTarea(unittest.TestCase):
    def test_windows(self):
        orden = construir("revertir_tarea", win(taskName="\\Actualizador0"), sistema="windows")
        self.assertEqual(orden.comando, "kronos-revertir-tarea")
        self.assertEqual(orden.argumentos, ("aplicar", "\\Actualizador0"))
        reversion = construir_reversion("revertir_tarea", win(taskName="\\Actualizador0"), sistema="windows")
        self.assertEqual(reversion.argumentos, ("habilitar", "\\Actualizador0"))

    def test_windows_en_carpeta_y_con_espacios(self):
        tarea = "\\Carpeta Nueva\\Actualizar Office (diaria)"
        self.assertEqual(construir("revertir_tarea", win(taskName=tarea), sistema="windows").argumentos[1], tarea)

    def test_windows_rechazadas(self):
        for tarea in (
            "Actualizador0",  # sin la barra inicial
            "\\..\\x",
            "\\\\a\\\\\\\\b",  # separador doble, tal como lo entrega Wazuh
            "\\a\\",
            "\\a&b",
            "\\a\"b",
            "\\a|b",
            "\\a%x%",
            "\\" + "a" * 240,
        ):
            with self.subTest(tarea=tarea), self.assertRaises(OrdenInvalida):
                construir("revertir_tarea", win(taskName=tarea), sistema="windows")

    def test_windows_sin_nombre(self):
        with self.assertRaises(ArgumentoFaltante):
            construir("revertir_tarea", win(image="C:\\Users\\Public\\x.exe"), sistema="windows")

    def test_linux_cron_y_timer(self):
        for ruta in (
            "/etc/crontab",
            "/etc/cron.d/actualizador",
            "/etc/cron.hourly/x",
            "/var/spool/cron/crontabs/labadmin",
            "/etc/systemd/system/actualizador.timer",
        ):
            with self.subTest(ruta=ruta):
                orden = construir("revertir_tarea", linux(syscheck={"path": ruta}), sistema="linux")
                self.assertEqual(orden.argumentos, ("aplicar", ruta))

    def test_linux_rechazadas(self):
        for ruta in (
            "/etc/passwd",
            "/etc/crontab.bak",
            "/etc/cron.d",
            "/etc/systemd/system/sshd.service",
            "/etc/cron.d/../passwd",
            "/tmp/cron.d/x",
        ):
            with self.subTest(ruta=ruta), self.assertRaises(OrdenInvalida):
                construir("revertir_tarea", linux(syscheck={"path": ruta}), sistema="linux")

    def test_linux_sin_archivo(self):
        with self.assertRaises(ArgumentoFaltante):
            construir("revertir_tarea", linux(data={"srcip": "198.51.100.9"}), sistema="linux")


class TerminarProceso(unittest.TestCase):
    def test_lleva_el_pid_y_el_ejecutable(self):
        ruta = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        orden = construir("terminar_proceso", win(processId="4312", image=ruta), sistema="windows")
        # Un programa de C:\Windows se puede terminar, aunque no se ponga en cuarentena.
        self.assertEqual(orden.argumentos, ("aplicar", "4312", ruta))

    def test_linux_desde_auditd(self):
        alerta = linux(data={"audit": {"pid": "2211", "exe": "/tmp/.x/minero"}})
        self.assertEqual(construir("terminar_proceso", alerta, sistema="linux").argumentos, ("aplicar", "2211", "/tmp/.x/minero"))

    def test_no_usa_syscheck(self):
        alerta = win(processId="4312")
        alerta["syscheck"] = {"path": "C:\\Users\\Public\\upd.exe"}
        with self.assertRaises(ArgumentoFaltante):
            construir("terminar_proceso", alerta, sistema="windows")

    def test_sin_ejecutable_es_argumento_faltante(self):
        with self.assertRaises(ArgumentoFaltante):
            construir("terminar_proceso", win(processId="4312"), sistema="windows")

    def test_ejecutable_invalido(self):
        for ruta in ("C:\\a;b.exe", "C:\\PROGRA~1\\x.exe", "/tmp/x", "powershell.exe"):
            with self.subTest(ruta=ruta), self.assertRaises(OrdenInvalida):
                construir("terminar_proceso", win(processId="4312", image=ruta), sistema="windows")


class ArgumentoFaltanteEnTodas(unittest.TestCase):
    def test_sin_campo_es_argumento_faltante(self):
        for accion in (
            "bloquear_ip",
            "deshabilitar_cuenta",
            "cerrar_sesion",
            "terminar_proceso",
            "detener_servicio",
            "cuarentena",
            "bloquear_destino",
            "limitar_conexiones",
            "revertir_tarea",
        ):
            with self.subTest(accion=accion), self.assertRaises(ArgumentoFaltante):
                construir(accion, {"agent": {"id": "002"}, "data": {}}, sistema="windows")

    def test_el_manager_va_antes_que_el_argumento(self):
        with self.assertRaises(OrdenInvalida) as caso:
            construir("cuarentena", {"agent": {"id": "000"}}, sistema="linux")
        self.assertNotIsInstance(caso.exception, ArgumentoFaltante)

    def test_valor_invalido_no_es_argumento_faltante(self):
        with self.assertRaises(OrdenInvalida) as caso:
            construir("bloquear_destino", win(destinationIp="no-es-ip"), sistema="windows")
        self.assertNotIsInstance(caso.exception, ArgumentoFaltante)


class IpProtegidas(unittest.TestCase):
    def test_lee_y_normaliza(self):
        self.assertEqual(
            leer_ip_protegidas(" 203.0.113.10, ::ffff:10.0.50.1 ,,2001:DB8::1"),
            frozenset({"203.0.113.10", "10.0.50.1", "2001:db8::1"}),
        )

    def test_vacia(self):
        self.assertEqual(leer_ip_protegidas(""), frozenset())

    def test_invalida_no_arranca(self):
        for texto in ("203.0.113.10;id", "203.0.113.0/24", "manager"):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                leer_ip_protegidas(texto)


if __name__ == "__main__":
    unittest.main()


class BarrasDuplicadasDeWazuh(unittest.TestCase):
    """El decodificador eventchannel de Wazuh duplica las barras de los campos de Windows."""

    def test_tarea_con_barras_duplicadas(self):
        orden = construir("revertir_tarea", win(taskName="\\\\Actualizador"), sistema="windows")
        self.assertEqual(orden.argumentos[1], "\\Actualizador")

    def test_tarea_en_carpeta_con_barras_duplicadas(self):
        orden = construir(
            "revertir_tarea", win(taskName="\\\\Carpeta\\\\Actualizador"), sistema="windows"
        )
        self.assertEqual(orden.argumentos[1], "\\Carpeta\\Actualizador")

    def test_ruta_con_barras_duplicadas(self):
        orden = construir(
            "cuarentena", win(image="C:\\\\Users\\\\Public\\\\b.exe"), sistema="windows"
        )
        self.assertEqual(orden.argumentos[1], "C:\\Users\\Public\\b.exe")

    def test_barras_simples_no_cambian(self):
        orden = construir("revertir_tarea", win(taskName="\\Actualizador"), sistema="windows")
        self.assertEqual(orden.argumentos[1], "\\Actualizador")
