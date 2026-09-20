# Plan del piloto — lab de genética, lunes

Este documento está en español a propósito: lo van a usar dos personas en un
salón colombiano, igual que la interfaz. El reporte de resultados va en inglés.

---

## 1. Antes del domingo en la noche

**Conseguir la lista del lab.** Nombres de los estudiantes, en Excel o como
sea que te la pase. Sin esto no hay nada que hacer.

**Exportar a CSV.** En Numbers o Excel: Archivo → Exportar a → CSV.

**Generar los códigos.**

```
python3 generate_codes.py lista-lab.csv "Genetica - Lab"
```

**Imprimir los papelitos.** Abre `codes_to_print.html`, Cmd+P, imprime,
corta. Guárdalos en orden alfabético para repartirlos rápido.

**Subir la lista real a Render** — este es el paso que se olvida:

1. Entra a tu servicio en render.com
2. Menú izquierdo → **Environment**
3. Sección **Secret Files** → **Add Secret File**
4. Filename: `roster.csv`
5. Contents: pega el contenido completo del `roster.csv` que generó el script
6. Save

Render lo coloca junto al código al arrancar. Nunca pasa por GitHub, así que
los nombres reales no quedan públicos.

**Desplegar y verificar.** Después de guardar el secret file, Render
redespliega. Espera a que diga "Live" y entra a la URL. En los logs de Render
debe decir `Course roster loaded. New students: N`, donde N es el número real
de estudiantes del lab.

> Si dice `New students: 0`, la base de datos ya tenía la lista vieja de
> prueba. En ese caso hay que borrarla, y la forma más simple en el plan
> gratuito es esperar a que el servicio se reinicie solo, o hacer un
> "Manual Deploy → Clear build cache & deploy".

**Probar el flujo completo en producción**, con tu propio teléfono y un
código real de la lista. Regístrate, inicia sesión de asistencia, escanea.
Si funciona con uno, funciona con veinte.

**Definir la contraseña que va a usar tu mamá** y dársela. Que no sea la de
Uninorte. 

**Y a partir de ahí, congelar.** El plan gratuito de Render borra la base de
datos en cada despliegue. Desde que subes la lista real hasta que descargas
el CSV al salir del salón, no hagas `git push`, no cambies el Secret File,
no toques nada en Render. Cualquiera de esas cosas dispara un despliegue y
se pierden todos los registros y toda la asistencia.

Si necesitas arreglar algo del código, hazlo antes de subir la lista, o
después de descargar el CSV. Nunca en el medio.

---

## 2. El día, antes de entrar al salón

**Despierta el servicio.** El plan gratuito de Render duerme por inactividad
y la primera petición puede tardar casi un minuto. Abre la URL **diez minutos
antes** de que empiece la clase y déjala abierta.

**Lleva un plan B en papel.** Una lista impresa con los nombres, para marcar
a mano si algo se cae. No es pesimismo: es lo que permite que la clase siga
si falla el WiFi.

**Carga el computador de tu mamá** y confirma que el proyector conecta.

---

## 3. El minuto a minuto

**Paso 1 — La medición base, antes de mencionar el sistema.**

Tu mamá llama a lista como siempre lo hace. Tú cronometras con el celular,
desde que dice el primer nombre hasta que termina. **Anota el número exacto
y cuántos estudiantes había.**

Este es el dato más importante de todo el proyecto. Sin él, cualquier cosa
que digas después es una estimación.

**Paso 2 — Explicar, en menos de un minuto.**

Tu mamá les dice: que es un sistema de asistencia que está probando, que lo
construyó un estudiante de colegio, que no recoge ubicación ni datos
biométricos, solo el código y la hora. Y que la asistencia de hoy ya quedó
tomada por la vía normal, así que esto no afecta a nadie.

Esa última frase importa: quita la presión y hace que nadie sienta que su
nota depende de un experimento.

**Paso 3 — Repartir los papelitos.**

Uno por persona, en la mano. No los leas en voz alta. Si sobran papelitos,
son los ausentes: guárdalos.

**Paso 4 — Registro.**

Proyecta el QR de registro (`/qr-register-page`). Cada uno escanea, escribe
su código, confirma su nombre. **Cronometra cuánto tarda el último en
terminar.**

Aquí es donde más probable es que algo se trabe. Ten paciencia y anota qué
falla: teléfonos sin datos, códigos mal copiados, gente que no entiende la
pantalla.

**Paso 5 — Asistencia.**

Vuelve al inicio, "Iniciar asistencia", proyecta el QR rotativo.
**Cronometra desde que aparece el QR hasta que el contador deja de subir.**

**Paso 6 — Los que faltaron.**

Con el botón de agregar manualmente, mete a quien no pudo. Anota cuántos
fueron y por qué.

**Paso 7 — Terminar y descargar.**

Botón rojo, y **descarga el CSV inmediatamente**. En el plan gratuito de
Render los datos se pierden si el servicio se reinicia. Descárgalo antes de
salir del salón.

---

## 4. Qué anotar

Lleva una libreta o una nota en el celular con estos campos vacíos, listos
para llenar:

- Estudiantes presentes: ____
- Tiempo del llamado a lista tradicional: ____
- Tiempo del registro inicial: ____
- Tiempo de la asistencia con el sistema: ____
- Cuántos se registraron sin problema: ____
- Cuántos necesitaron ayuda: ____
- Cuántos hubo que agregar a mano, y por qué: ____
- Qué preguntó la gente: ____
- Qué dijo tu mamá después: ____

Las dos últimas valen tanto como los números. Una pregunta repetida por
cinco estudiantes es un problema de diseño.

---

## 5. Si algo falla

**El WiFi no funciona.** Que usen datos móviles. Si tampoco, se cae la
prueba: pasa al plan B en papel y lo intentas otro día. Anótalo como
resultado, no como fracaso — la dependencia de conectividad es un hallazgo
real.

**Un estudiante no puede registrarse.** No te detengas a depurar en vivo.
Anota su nombre y el mensaje que le salió, agrégalo a mano, y sigue. Lo
investigas después.

**El servicio está dormido y no carga.** Espera un minuto completo antes de
tocar nada. Si sigue sin cargar, plan B en papel.

**Se cierra el navegador.** No pasa nada: entra otra vez, "Ver clases
anteriores", y ahí está la sesión con su link de descarga. Eso lo
construimos justamente para esto.

---

## 6. Apenas salgas del salón

Antes de que se te olvide, mientras está fresco:

- Verifica que el CSV está descargado y tiene los datos
- Escribe la entrada del día en `experiments.md`
- Toma foto de tus notas

Y si tu mamá dijo algo sobre qué le gustaría que el sistema hiciera, anótalo
textual. Eso es lo que define qué se construye después — no lo que se te
ocurra a ti frente al computador.
