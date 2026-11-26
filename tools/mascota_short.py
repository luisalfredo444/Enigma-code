#!/usr/bin/env python3
"""Monta un Short vertical estilo "mascota + palabra a palabra" para el canal Enigma.

Uso:
    python3 tools/mascota_short.py proyecto.json

El JSON del proyecto (rutas relativas al propio JSON):
{
  "voice": "voz.mp3",                 # narración (mp3/wav)
  "out": "short.mp4",                 # salida 1080x1920
  "keywords": ["vuelo", "nunca"],     # palabras resaltadas en amarillo (opcional)
  "music": "../../audio/musica-detective.mp3",  # música de fondo en bucle (opcional)
  "music_volume": 0.5,                # 0-1, volumen de la música (opcional)
  "whoosh": "../../audio/whoosh.mp3", # efecto en cada cambio de escena (opcional)
  "lines": [                          # una entrada por frase del guion, en orden
    {"text": "En 1945...",            # lo que se muestra en subtítulos
     "spoken": "En mil novecientos...",  # (opcional) cómo se pronuncia, para medir duración
     "images": ["01.png", "02.png"]}  # escenas que cubren esa frase (se reparten el tiempo)
  ]
}

Sincronización: detecta las pausas de la voz y reparte las frases entre los tramos
hablados; dentro de cada frase, cada palabra dura en proporción a sus letras.
No necesita transcripción ni conexión a internet.
"""
import json, os, re, subprocess, sys, tempfile

W, H, FPS = 1080, 1920, 30
FONT_DIR = "/usr/share/fonts/opentype/inter"
GREEN, YELLOW = "&H3DFF6B&", "&H2DD7FF&"  # ASS usa BGR


def run(cmd):
    subprocess.run(cmd, check=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def speech_spans(voice, total):
    """Tramos hablados [(ini, fin)] separados por pausas >= 0.15 s."""
    r = subprocess.run(["ffmpeg", "-i", voice, "-af", "silencedetect=n=-40dB:d=0.15", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    spans, t = [], 0.0
    for s, e in zip(starts, ends + [total] * (len(starts) - len(ends))):
        if s - t > 0.05:
            spans.append((t, s))
        t = e
    if total - t > 0.05:
        spans.append((t, total))
    return spans


def weight(text):
    return sum(len(w) + 1 for w in text.split())


def align_lines(lines, spans):
    """Devuelve (ini, fin) por frase. Si hay tantos tramos como frases, 1:1;
    si no, coloca cada corte de frase en la pausa más cercana por proporción."""
    if len(spans) == len(lines):
        return [[sp] for sp in spans]
    n, L = len(spans), len(lines)
    if n < L:
        raise SystemExit(f"Solo hay {n} tramos de voz para {L} frases: une frases en el JSON.")
    w = [weight(l.get("spoken", l["text"])) for l in lines]
    rate = sum(b - a for a, b in spans) / sum(w)  # segundos hablados por unidad de peso
    talk = lambda i, j: sum(b - a for a, b in spans[i:j])  # habla en tramos [i, j)
    # DP: cada frase ocupa un grupo contiguo de tramos; minimiza el error relativo de duración
    INF = float("inf")
    cost = [[INF] * (n + 1) for _ in range(L + 1)]
    back = [[0] * (n + 1) for _ in range(L + 1)]
    cost[0][0] = 0.0
    for k in range(1, L + 1):
        exp = w[k - 1] * rate
        for j in range(k, n - (L - k) + 1):
            for i in range(k - 1, j):
                if cost[k - 1][i] == INF:
                    continue
                c = cost[k - 1][i] + ((talk(i, j) - exp) / exp) ** 2
                if c < cost[k][j]:
                    cost[k][j], back[k][j] = c, i
    groups, j = [], n
    for k in range(L, 0, -1):
        i = back[k][j]; groups.append((i, j)); j = i
    groups.reverse()
    return [spans[i:j] for i, j in groups]


def ts(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def build_words(lines, line_spans):
    """Lista de (ini, fin, palabra) con tiempo proporcional a las letras pronunciadas,
    contando solo el tiempo hablado (las pausas dentro de la frase se saltan)."""
    words = []
    for line, sps in zip(lines, line_spans):
        talk = sum(b - a for a, b in sps)

        def real(x):  # segundos hablados desde el inicio de la frase -> instante real
            for a, b in sps:
                if x <= b - a:
                    return a + x
                x -= b - a
            return sps[-1][1]
        shown = line["text"].split()
        spoken = line.get("spoken")
        # si hay versión pronunciada, reparte su peso total proporcionalmente
        scale = weight(spoken) / weight(line["text"]) if spoken else 1.0
        ws = [(len(w) + 1) * scale for w in shown]
        tot, acc = sum(ws), 0.0
        for w, x in zip(shown, ws):
            t0 = talk * acc / tot; acc += x
            words.append([real(t0), real(talk * acc / tot - 1e-6), w])
    for i in range(len(words) - 1):  # tapa huecos cortos
        if words[i + 1][0] - words[i][1] < 0.6:
            words[i][1] = words[i + 1][0]
    words[-1][1] += 0.6
    return words


def write_ass(words, keywords, path):
    kw = {k.lower() for k in keywords}
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Glow,Inter Black,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,-1,0,0,100,100,2,0,1,10,0,5,60,60,0,1
Style: Word,Inter Black,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,-1,0,0,100,100,2,0,1,7,5,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    pos = f"\\pos({W // 2},{int(H * 0.56)})"
    pop = "\\fscx70\\fscy70\\t(0,80,\\fscx108\\fscy108)\\t(80,150,\\fscx100\\fscy100)"
    with open(path, "w") as f:
        f.write(hdr)
        for i, (a, b, w) in enumerate(words):
            clean = re.sub(r"[^\wáéíóúüñ]", "", w.lower())
            col = YELLOW if clean in kw else GREEN
            txt = re.sub(r"[.,:;…]+", "", w).upper() or w.upper()
            f.write(f"Dialogue: 0,{ts(a)},{ts(b)},Glow,,0,0,0,,{{{pos}{pop}\\blur12\\3c{col}\\1a&HFF&}}{txt}\n")
            f.write(f"Dialogue: 1,{ts(a)},{ts(b)},Word,,0,0,0,,{{{pos}{pop}\\1c{col}}}{txt}\n")


# Movimientos de cámara (expresiones de zoompan; P = progreso 0..1 del plano).
# La imagen se escala a 2x, así que hay margen para paneos sin bordes negros.
MOVES = {
    "zoom_in":  ("1.04+0.16*P", "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"),
    "zoom_out": ("1.20-0.16*P", "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"),
    "pan_der":  ("1.22", "(iw-iw/zoom)*P", "(ih-ih/zoom)/2"),
    "pan_izq":  ("1.22", "(iw-iw/zoom)*(1-P)", "(ih-ih/zoom)/2"),
    "pan_arr":  ("1.18", "(iw-iw/zoom)/2", "(ih-ih/zoom)*(1-P)"),
    "pan_aba":  ("1.18", "(iw-iw/zoom)/2", "(ih-ih/zoom)*P"),
}
ORDER = ["zoom_in", "pan_der", "zoom_out", "pan_arr", "zoom_in", "pan_izq", "zoom_out", "pan_aba"]


def scene_clips(lines, line_times, base, tmp, total):
    """Reparte el tiempo de cada frase entre sus imágenes; cortes en los límites.
    Cada plano lleva un movimiento distinto, golpe de zoom al entrar y balanceo suave.
    Devuelve (clips, instantes de corte)."""
    shots = []
    for i, (line, (a, b)) in enumerate(zip(lines, line_times)):
        end = line_times[i + 1][0] if i + 1 < len(lines) else total
        imgs = line["images"]
        step = (end - a) / len(imgs)
        for j, img in enumerate(imgs):
            shots.append([os.path.join(base, img), a + j * step, a + (j + 1) * step])
    shots[0][1] = 0.0
    shots[-1][2] = total
    files, cuts = [], []
    for n, (img, a, b) in enumerate(shots):
        fr = max(1, round(b * FPS) - round(a * FPS))  # sin deriva acumulada
        z, x, y = MOVES[ORDER[n % len(ORDER)]]
        P = f"(on/{fr})"
        punch = "(1+0.10*max(0,1-on/6))"           # golpe de zoom en los primeros 6 frames
        wob_x, wob_y = "10*sin(on/11)", "8*sin(on/7+1)"  # cámara en mano suave
        z = f"({z.replace('P', P)})*{punch}"
        x = f"max(0,min(iw-iw/zoom,{x.replace('P', P)}+{wob_x}))"
        y = f"max(0,min(ih-ih/zoom,{y.replace('P', P)}+{wob_y}))"
        out = os.path.join(tmp, f"s{n:03d}.mp4")
        vf = (f"scale={W*2}:-2,crop={W*2}:{H*2},zoompan=z='{z}':x='{x}':y='{y}':"
              f"d={fr}:s={W}x{H}:fps={FPS},format=yuv420p")
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", img, "-vf", vf, "-frames:v", str(fr),
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", out])
        files.append(out)
        if n:
            cuts.append(round(a * FPS) / FPS)
    return files, cuts


def mix_audio(voice, total, cuts, music, whoosh, music_vol, out):
    """Voz al frente; música en bucle que se agacha cuando hay voz; whoosh en cada corte."""
    inputs = ["-i", voice]
    fc = [f"[0]loudnorm=I=-14:TP=-1.5,aresample=44100,apad=whole_dur={total},asplit=2[v][key]"]
    mixes = ["[v]"]
    k = 1
    if music:
        inputs += ["-stream_loop", "-1", "-i", music]
        fc.append(f"[{k}]aresample=44100,atrim=0:{total},loudnorm=I=-16,volume={music_vol},"
                  f"afade=t=in:d=0.5,afade=t=out:st={total-2.5}:d=2.5[m0]")
        fc.append("[m0][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[m]")
        mixes.append("[m]"); k += 1
    else:
        fc.append("[key]anullsink")
    if whoosh and cuts:
        inputs += ["-i", whoosh]
        n = len(cuts)
        fc.append(f"[{k}]aresample=44100,volume=0.35,asplit={n}" + "".join(f"[w{i}]" for i in range(n)))
        for i, t in enumerate(cuts):
            d = max(0, int((t - 0.25) * 1000))
            fc.append(f"[w{i}]adelay={d}|{d}[wd{i}]")
        fc.append("".join(f"[wd{i}]" for i in range(n)) + f"amix={n}:normalize=0[w]")
        mixes.append("[w]")
    fc.append("".join(mixes) + f"amix={len(mixes)}:normalize=0:duration=first,alimiter=limit=0.95[a]")
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", "[a]", "-t", str(total), "-ac", "2", out])


def main(cfg_path):
    base = os.path.dirname(os.path.abspath(cfg_path))
    cfg = json.load(open(cfg_path))
    voice = os.path.join(base, cfg["voice"])
    out = os.path.join(base, cfg.get("out", "short.mp4"))
    lines = cfg["lines"]
    vdur = duration(voice)
    total = round(vdur + 1.0, 2)
    spans = speech_spans(voice, vdur)
    line_spans = align_lines(lines, spans)
    line_times = [(sps[0][0], sps[-1][1]) for sps in line_spans]
    print(f"{len(spans)} tramos de voz, {len(lines)} frases")
    words = build_words(lines, line_spans)
    with tempfile.TemporaryDirectory() as tmp:
        ass = os.path.join(tmp, "subs.ass")
        write_ass(words, cfg.get("keywords", []), ass)
        clips, cuts = scene_clips(lines, line_times, base, tmp, total)
        lst = os.path.join(tmp, "list.txt")
        open(lst, "w").write("".join(f"file '{c}'\n" for c in clips))
        mudo = os.path.join(tmp, "mudo.mp4")
        run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", mudo])
        mix = os.path.join(tmp, "mix.wav")
        opt = lambda k: os.path.join(base, cfg[k]) if cfg.get(k) else None
        mix_audio(voice, total, cuts, opt("music"), opt("whoosh"), cfg.get("music_volume", 0.5), mix)
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", mudo, "-i", mix,
             "-vf", f"ass={ass}:fontsdir={FONT_DIR}", "-map", "0:v", "-map", "1:a",
             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-t", str(total), "-movflags", "+faststart", out])
    print("listo:", out, f"{total:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1])
