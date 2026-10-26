#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compresor Inteligente de PDF — Proyecto de PDF
Modo interactivo amigable en Terminal (.command) + Motor de compresión en Alta Definición y Máximo Ahorro.
"""

import os
import sys
import re
import zlib
import time
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_ENTRADA = os.path.join(BASE_DIR, "1_Entrada")
DIR_SALIDA = os.path.join(BASE_DIR, "2_Comprimidos")
DIR_PROCESADOS = os.path.join(BASE_DIR, "3_Originales_Procesados")

for d in (DIR_ENTRADA, DIR_SALIDA, DIR_PROCESADOS):
    os.makedirs(d, exist_ok=True)

# Colores ANSI para una Terminal limpia y amigable
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_AMBER = "\033[38;5;214m"
C_TEAL = "\033[38;5;43m"
C_BLUE = "\033[38;5;75m"
C_GREEN = "\033[38;5;78m"
C_RED = "\033[38;5;203m"
C_WHITE = "\033[97m"


def format_mb(size_bytes):
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def print_progress_bar(pct, label=""):
    width = 28
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r   {C_TEAL}[{bar}] {pct:3d}%{C_RESET}  {label:<45}")
    sys.stdout.flush()


def compress_pdf_file(input_path, output_path, bpc_target=4, show_cli_progress=True):
    t0 = time.time()
    with open(input_path, "rb") as f:
        data = f.read()

    orig_size = len(data)
    if show_cli_progress:
        print_progress_bar(8, "Analizando estructura del PDF...")

    obj_pattern = re.compile(rb"(\d+)\s+0\s+obj\s*(.*?)\s*endobj", re.S)
    stream_pattern = re.compile(rb"^(<<.*?>>)\s*stream\r?\n(.*?)\r?\nendstream$", re.S)

    palettes = {}
    raw_objs = {}
    for m in obj_pattern.finditer(data):
        oid = int(m.group(1))
        body = m.group(2)
        raw_objs[oid] = body
        sm = stream_pattern.match(body)
        if sm:
            hdr, sdata = sm.group(1), sm.group(2)
            if b"/Subtype/Image" not in hdr and len(sdata) < 2000:
                try:
                    pal = zlib.decompress(sdata) if b"FlateDecode" in hdr else sdata
                    if len(pal) <= 768 and len(pal) % 3 == 0:
                        palettes[oid] = pal
                except Exception:
                    pass

    new_objs = {}
    optimized_images = 0
    total_objs = max(len(raw_objs), 1)

    for idx, (oid, body) in enumerate(raw_objs.items()):
        if show_cli_progress and idx % 150 == 0:
            pct = 12 + int((idx / total_objs) * 80)
            print_progress_bar(pct, f"Optimizando tablas ({idx}/{total_objs})...")

        sm = stream_pattern.match(body)
        if not sm:
            new_objs[oid] = body
            continue

        hdr, sdata = sm.group(1), sm.group(2)
        if b"/Subtype/Image" in hdr and b"/Indexed" in hdr and b"/FlateDecode" in hdr:
            w_m = re.search(rb"/Width\s+(\d+)", hdr)
            h_m = re.search(rb"/Height\s+(\d+)", hdr)
            pal_m = re.search(rb"\[/Indexed/DeviceRGB\s+(\d+)\s+(\d+)\s+0\s+R\]", hdr)
            if w_m and h_m and pal_m:
                w = int(w_m.group(1))
                h = int(h_m.group(1))
                pal_id = int(pal_m.group(2))
                if w >= 1700 and pal_id in palettes and bpc_target in (2, 4):
                    pal = palettes[pal_id]
                    try:
                        raw_pixels = zlib.decompress(sdata)
                    except Exception:
                        raw_pixels = b""
                    if len(raw_pixels) == w * h:
                        if bpc_target == 4:
                            lut = bytes(
                                round((0.299 * pal[i * 3] + 0.587 * pal[i * 3 + 1] + 0.114 * pal[i * 3 + 2]) / 17.0)
                                for i in range(len(pal) // 3)
                            )
                            lut = lut + bytes(256 - len(lut))
                            mapped = raw_pixels.translate(lut)
                            if w % 2 == 0:
                                packed = bytes((a << 4) | b for a, b in zip(mapped[0::2], mapped[1::2]))
                            else:
                                packed = bytearray()
                                for y in range(h):
                                    row = mapped[y * w : (y + 1) * w]
                                    if len(row) % 2 == 1:
                                        row = row + b"\x00"
                                    packed.extend((a << 4) | b for a, b in zip(row[0::2], row[1::2]))
                                packed = bytes(packed)
                            comp = zlib.compress(packed, 9)
                            new_hdr = re.sub(
                                rb"/ColorSpace\[/Indexed/DeviceRGB\s+\d+\s+\d+\s+0\s+R\]",
                                b"/ColorSpace/DeviceGray",
                                hdr,
                            )
                            new_hdr = re.sub(rb"/BitsPerComponent\s+8", b"/BitsPerComponent 4", new_hdr)
                            new_hdr = re.sub(rb"/Length\s+\d+", f"/Length {len(comp)}".encode("ascii"), new_hdr)
                            new_objs[oid] = new_hdr + b"\nstream\n" + comp + b"\nendstream"
                            optimized_images += 1
                            continue
                        elif bpc_target == 2:
                            lut = bytes(
                                round((0.299 * pal[i * 3] + 0.587 * pal[i * 3 + 1] + 0.114 * pal[i * 3 + 2]) / 85.0)
                                for i in range(len(pal) // 3)
                            )
                            lut = lut + bytes(256 - len(lut))
                            mapped = raw_pixels.translate(lut)
                            if w % 4 == 0:
                                packed = bytes(
                                    (a << 6) | (b << 4) | (c << 2) | d
                                    for a, b, c, d in zip(mapped[0::4], mapped[1::4], mapped[2::4], mapped[3::4])
                                )
                            else:
                                packed = bytearray()
                                pad = (4 - (w % 4)) % 4
                                for y in range(h):
                                    row = mapped[y * w : (y + 1) * w] + (b"\x00" * pad)
                                    packed.extend(
                                        (a << 6) | (b << 4) | (c << 2) | d
                                        for a, b, c, d in zip(row[0::4], row[1::4], row[2::4], row[3::4])
                                    )
                                packed = bytes(packed)
                            comp = zlib.compress(packed, 9)
                            new_hdr = re.sub(
                                rb"/ColorSpace\[/Indexed/DeviceRGB\s+\d+\s+\d+\s+0\s+R\]",
                                b"/ColorSpace/DeviceGray",
                                hdr,
                            )
                            new_hdr = re.sub(rb"/BitsPerComponent\s+8", b"/BitsPerComponent 2", new_hdr)
                            new_hdr = re.sub(rb"/Length\s+\d+", f"/Length {len(comp)}".encode("ascii"), new_hdr)
                            new_objs[oid] = new_hdr + b"\nstream\n" + comp + b"\nendstream"
                            optimized_images += 1
                            continue

        if b"/FlateDecode" in hdr and b"/Predictor" not in hdr:
            try:
                raw_s = zlib.decompress(sdata)
                comp = zlib.compress(raw_s, 9)
                if len(comp) < len(sdata):
                    new_hdr = re.sub(rb"/Length\s+\d+", f"/Length {len(comp)}".encode("ascii"), hdr)
                    new_objs[oid] = new_hdr + b"\nstream\n" + comp + b"\nendstream"
                    continue
            except Exception:
                pass

        new_objs[oid] = body

    if show_cli_progress:
        print_progress_bar(95, "Guardando archivo PDF reducido...")

    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    max_oid = max(new_objs.keys()) if new_objs else 0
    for oid in sorted(new_objs.keys()):
        offsets[oid] = len(out)
        out.extend(f"{oid} 0 obj\n".encode("ascii"))
        out.extend(new_objs[oid])
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {max_oid + 1}\n0000000000 65535 f \n".encode("ascii"))
    for oid in range(1, max_oid + 1):
        if oid in offsets:
            out.extend(f"{offsets[oid]:010d} 00000 n \n".encode("ascii"))
        else:
            out.extend(b"0000000000 65535 f \n")

    root_m = re.search(rb"/Root\s+(\d+\s+0\s+R)", data)
    info_m = re.search(rb"/Info\s+(\d+\s+0\s+R)", data)
    trailer_dict = f"<< /Size {max_oid + 1}"
    if root_m:
        trailer_dict += f' /Root {root_m.group(1).decode("ascii")}'
    if info_m:
        trailer_dict += f' /Info {info_m.group(1).decode("ascii")}'
    trailer_dict += " >>"

    out.extend(f"trailer\n{trailer_dict}\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))

    with open(output_path, "wb") as f:
        f.write(out)

    new_size = len(out)
    elapsed = time.time() - t0
    if show_cli_progress:
        print_progress_bar(100, "¡Completado!")
        print()

    return {
        "orig_size": orig_size,
        "new_size": new_size,
        "optimized_images": optimized_images,
        "elapsed": elapsed,
    }


def get_pending_pdfs():
    return [
        os.path.join(DIR_ENTRADA, f)
        for f in sorted(os.listdir(DIR_ENTRADA))
        if f.lower().endswith(".pdf") and not f.startswith(".")
    ]


def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


def print_banner():
    clear_screen()
    print(f"{C_AMBER}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C_RESET}")
    print(f"  {C_BOLD}{C_WHITE}🚇  OPTIMIZADOR TÉCNICO DE REPORTES PDF — LÍNEA 2{C_RESET}")
    print(f"  {C_DIM}Reduce el peso sin perder nitidez en textos, logos ni gráficos a color{C_RESET}")
    print(f"{C_AMBER}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C_RESET}\n")


def run_batch(mode="both", move_orig=True):
    pdfs = get_pending_pdfs()
    if not pdfs:
        print(f"  {C_RED}⚠ No hay archivos PDF pendientes en '1_Entrada'.{C_RESET}")
        print(f"  Coloca un PDF en la carpeta {C_BOLD}1_Entrada{C_RESET} e inténtalo de nuevo.\n")
        return

    for p in pdfs:
        fname = os.path.basename(p)
        clean_base = re.sub(r"\(VIRGEN\)", "", os.path.splitext(fname)[0], flags=re.IGNORECASE).strip()
        print(f"  📄 {C_BOLD}{fname}{C_RESET} ({format_mb(os.path.getsize(p))})")

        if mode in ("4", "both"):
            out_hd = os.path.join(DIR_SALIDA, f"{clean_base}_HD.pdf")
            r4 = compress_pdf_file(p, out_hd, bpc_target=4, show_cli_progress=True)
            pct4 = (1 - r4["new_size"] / r4["orig_size"]) * 100
            print(
                f"     {C_GREEN}✔ Opción 1 (HD 4-bit):{C_RESET} {os.path.basename(out_hd)} "
                f"→ {C_BOLD}{format_mb(r4['new_size'])}{C_RESET} (-{pct4:.1f}% en {r4['elapsed']:.1f}s)"
            )

        if mode in ("2", "both"):
            out_max = os.path.join(DIR_SALIDA, f"{clean_base}_MAX.pdf")
            r2 = compress_pdf_file(p, out_max, bpc_target=2, show_cli_progress=True)
            pct2 = (1 - r2["new_size"] / r2["orig_size"]) * 100
            print(
                f"     {C_GREEN}✔ Opción 2 (MAX 2-bit):{C_RESET} {os.path.basename(out_max)} "
                f"→ {C_BOLD}{format_mb(r2['new_size'])}{C_RESET} (-{pct2:.1f}% en {r2['elapsed']:.1f}s)"
            )

        if move_orig:
            shutil.move(p, os.path.join(DIR_PROCESADOS, fname))
            print(f"     {C_DIM}📦 Original guardado en '3_Originales_Procesados'{C_RESET}\n")


def interactive_terminal():
    while True:
        print_banner()
        pdfs = get_pending_pdfs()
        done_pdfs = [f for f in sorted(os.listdir(DIR_SALIDA)) if f.lower().endswith(".pdf")]

        print(f"  📂 {C_BOLD}Archivos en '1_Entrada' ({len(pdfs)}):{C_RESET}")
        if not pdfs:
            print(f"     {C_DIM}(Vacío — arrastra aquí tus PDFs para comprimirlos){C_RESET}")
        else:
            for p in pdfs:
                print(f"     • {os.path.basename(p)} ({format_mb(os.path.getsize(p))})")

        print(f"\n  ✅ {C_BOLD}Archivos listos en '2_Comprimidos' ({len(done_pdfs)}):{C_RESET}")
        for f in done_pdfs[:5]:
            sz = os.path.getsize(os.path.join(DIR_SALIDA, f))
            print(f"     • {f} ({format_mb(sz)})")
        if len(done_pdfs) > 5:
            print(f"     {C_DIM}... y {len(done_pdfs) - 5} más.{C_RESET}")

        print(f"\n{C_AMBER}──────────────────────────────────────────────────────────────────────────────{C_RESET}")
        print(f"  {C_BOLD}ELIGE UNA OPCIÓN:{C_RESET}")
        print(f"    {C_TEAL}[1]{C_RESET} Comprimir en {C_BOLD}Ambas Calidades{C_RESET} (Genera _HD 13.1 MB y _MAX 9.8 MB)")
        print(f"    {C_TEAL}[2]{C_RESET} Comprimir solo en {C_BOLD}Opción 1: Alta Definición (4-bit){C_RESET} (~13.1 MB)")
        print(f"    {C_TEAL}[3]{C_RESET} Comprimir solo en {C_BOLD}Opción 2: Máximo Ahorro (2-bit){C_RESET} (~9.8 MB)")
        print(f"    {C_TEAL}[4]{C_RESET} Activar {C_BOLD}Modo Automático{C_RESET} (Vigila '1_Entrada' continuamente)")
        print(f"    {C_BLUE}[5]{C_RESET} 🌐 Abrir {C_BOLD}Aplicación Web HTML{C_RESET} (Ideal para subir archivos y exportar)")
        print(f"    {C_BLUE}[6]{C_RESET} 📂 Abrir carpetas del proyecto en Finder")
        print(f"    {C_DIM}[0] Salir{C_RESET}")
        print(f"{C_AMBER}──────────────────────────────────────────────────────────────────────────────{C_RESET}")

        choice = input(f"\n  👉 Escribe un número (1-6) y presiona Enter: ").strip()

        if choice == "1":
            print()
            run_batch(mode="both", move_orig=True)
            input(f"  Presiona Enter para volver al menú...")
        elif choice == "2":
            print()
            run_batch(mode="4", move_orig=True)
            input(f"  Presiona Enter para volver al menú...")
        elif choice == "3":
            print()
            run_batch(mode="2", move_orig=True)
            input(f"  Presiona Enter para volver al menú...")
        elif choice == "4":
            print(f"\n  👀 {C_GREEN}Modo Automático activado.{C_RESET} Suelta cualquier PDF en '1_Entrada'.")
            print(f"  {C_DIM}(Presiona Ctrl + C para detener y volver al menú){C_RESET}\n")
            try:
                while True:
                    if get_pending_pdfs():
                        run_batch(mode="both", move_orig=True)
                    time.sleep(2)
            except KeyboardInterrupt:
                pass
        elif choice == "5":
            html_path = os.path.join(BASE_DIR, "index.html")
            subprocess.Popen(["open", html_path])
        elif choice == "6":
            subprocess.Popen(["open", BASE_DIR])
        elif choice == "0":
            print(f"\n  ¡Hasta luego!\n")
            break


if __name__ == "__main__":
    interactive_terminal()
