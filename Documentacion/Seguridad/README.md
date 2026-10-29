# 5. Seguridad

Cómo se protege la propia plataforma Kronos AI: amenazas, riesgos, políticas, control de acceso, manejo de
secretos y respuesta ante un incidente que la afecte.

| Código | Documento | Archivo | Contenido |
| :-: | :--- | :--- | :--- |
| 5.1 | Modelado de Amenazas (STRIDE) | [`Modelado-Amenazas-Stride.docx`](Modelado-Amenazas-Stride.docx) | Amenazas contra la plataforma, analizadas con STRIDE sobre un diagrama de flujo de datos con sus fronteras de confianza |
| 5.2 | Matriz de Evaluación y Gestión de Riesgos de Seguridad | [`Matriz-Riesgos-Seguridad.docx`](Matriz-Riesgos-Seguridad.docx) | Riesgos técnicos, operacionales y de negocio con probabilidad, impacto, controles, riesgo residual, tratamiento y responsable |
| 5.3 | Políticas de Seguridad de la Información y Gobernanza Cloud | [`Politicas-Seguridad-Gobernanza.docx`](Politicas-Seguridad-Gobernanza.docx) | Clasificación, cifrado en tránsito y en reposo, retención y eliminación, ubicación de los datos, proveedor, gestión del servidor y uso aceptable |
| 5.4 | Políticas de Control de Acceso y Gestión de Identidades (IAM) | [`Politicas-IAM.docx`](Politicas-IAM.docx) | Quién accede a cada sistema, con qué rol y cómo se autentica, y cómo se dan de alta, se revisan y se revocan los accesos |
| 5.5 | Gestión de Mínimo Privilegio y Bóveda de Secretos | [`Minimo-Privilegio-Secretos.docx`](Minimo-Privilegio-Secretos.docx) | Inventario de credenciales (sin valores), permiso mínimo de cada una, almacenamiento, rotación, revocación y qué hacer ante una filtración |
| 5.6 | Plan de Respuesta a Incidentes (IRP) | [`Plan-Respuesta-Incidentes.docx`](Plan-Respuesta-Incidentes.docx) | Roles, severidades, fases según NIST SP 800-61 y procedimientos ante un compromiso de la plataforma o una falla crítica |

La política para reportar vulnerabilidades está en [`.github/SECURITY.md`](../../.github/SECURITY.md).

Índice completo de la documentación: [`../README.md`](../README.md).
