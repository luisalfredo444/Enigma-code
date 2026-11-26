---
name: short-mascota
description: Crea un Short vertical para el canal Enigma con el formato "mascota + palabra a palabra" (la mascota detective en cada escena estilo cómic, cortes cada ~3 s, voz en off y subtítulos de una palabra en verde/amarillo neón). Úsala cuando pidan un Short/Reel/TikTok de Enigma "con la mascota", "estilo cartoon" o "como el de las Bermudas".
---

# Short con mascota — canal Enigma

Formato: 60–80 s, 1080x1920, ~20–25 escenas ilustradas (contorno grueso, colores planos)
donde siempre aparece la mascota, voz en off grave y una sola palabra en pantalla a la vez.

## Recursos fijos
- Mascota: `mascota/detective-enigma.png` (cabeza blanca redonda, cejas gruesas, fedora
  marrón con cinta morada, gabardina morada con botones dorados, colgante "?" dorado,
  zapatillas moradas). En Higgsfield su job de referencia es
  `bd6326f7-a096-4ad7-9291-8ee4672e7feb`; si no está disponible, súbela con
  `media_upload` + `media_confirm` y usa ese media_id.
- Voz: ElevenLabs, voz "Damián" (`BPwS5yO6aXvwg8auqNwS`), modelo `eleven_v4`, 1 toma.
- Montaje: `python3 tools/mascota_short.py proyectos/<tema>/proyecto.json`
- Ejemplo completo: `proyectos/bermudas/`.

## Pasos
1. **Guion** (150–190 palabras ≈ 70 s), en español, con hechos verificables:
   - Gancho en la 1.ª frase (qué es el misterio y por qué engancha).
   - 2–3 casos concretos con fecha/nombre/cifra.
   - Teorías populares en ráfaga.
   - "Pero aquí viene el giro" + la explicación real o el dato que lo complica.
   - Pregunta final + "Sígueme para más enigmas."
   - Una frase por línea. Para la voz, escribe números en letras ("mil novecientos
     cuarenta y cinco"); en subtítulos se pueden mostrar en cifras (campo `spoken`).
2. **Escenas**: 1 imagen por cada 3–4 s (≈22). Genera con Higgsfield
   `generate_image_batch`, modelo `nano_banana_2`, `aspect_ratio: "9:16"`,
   `use_unlim: false`, `medias: [{role: "image_references", value: <id mascota>}]`.
   Prompt base (añade la escena al final):
   > Vertical 9:16 cartoon illustration in bold thick black outlines and flat clean colors,
   > modern internet comic style, detailed background. The main character is EXACTLY the
   > cartoon mascot from the reference image (round white head, big black eyebrows, dark
   > brown fedora with purple band, long purple trench coat with gold buttons, gold
   > question-mark pendant, purple sneakers), shown large in the frame. Scene: the mascot is
   > <acción + lugar + expresión exagerada>. No text, no captions, no logos.
   Cada escena: la mascota HACIENDO algo que ilustre la frase (señalar, asustarse, leer con
   lupa…), con expresión exagerada. Coste ≈1,5 créditos/imagen.
3. **Voz**: `creative_generate_speech` con el guion completo (párrafos = pausas). No repitas
   la llamada si falla por "busy": espera y reintenta en otro turno.
4. **Descarga** voz e imágenes a `proyectos/<tema>/` (`sc/01.png`…). El entorno debe
   permitir `elevenlabsusercontent.com` y `d8j0ntlcm91z4.cloudfront.net`.
5. **proyecto.json**: `voice`, `out`, `keywords` (palabras en amarillo, en minúscula sin
   puntuación) y `lines` = cada frase del guion en orden, con `text`, `spoken` opcional e
   `images` (las escenas que la cubren; varias se reparten su tiempo).
6. **Monta** con el script. Comprueba el alineado (frases ↔ pausas) imprimiendo
   `align_lines` si dudas, y revisa fotogramas antes de entregar.
7. **Publicar** (solo si lo piden): Blotato → `blotato_create_presigned_upload_url`, PUT del
   mp4 (`database.blotato.io` permitido), `blotato_create_post` en la cuenta de YouTube
   "Enigma Plus" con título + #shorts, `containsSyntheticMedia: true`,
   `isMadeForKids: false`. Confirma cuenta y privacidad con el usuario.
