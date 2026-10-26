# Optimizador Técnico de Reportes PDF — Línea 2

Herramienta ligera para reducir el peso de reportes diarios en PDF (de ~34.5 MB a **13.1 MB** o **9.8 MB**) **sin perder nitidez** en tablas, textos vectoriales, logotipos ni gráficos estadísticos a color.

## 🌐 Uso Directo desde el Navegador (Windows / Mac / Móvil)

Puedes utilizar la aplicación web directamente desde GitHub Pages sin instalar nada:
👉 **[Abrir Optimizador Web de PDF](https://ardalaxdown.github.io/Reduce-el-peso-de-tus-reportes-PDF-sin-perdes-nitidez/)**

- **100% Privado y Local:** Los documentos PDF se procesan directamente en la memoria de tu navegador; ningún archivo se sube a servidores externos.
- **2 Perfiles de Compresión:**
  - **Opción 1 — Alta Definición (4-bit / HD):** Reduce ~62% del peso (34.5 MB → 13.1 MB) conservando 16 niveles de suavizado en bordes de letras y tablas.
  - **Opción 2 — Máximo Ahorro (2-bit / MAX):** Reduce ~72% del peso (34.5 MB → 9.8 MB) con 4 niveles de suavizado y gráficos a color intactos.

## 💻 Uso por Carpetas en Consola (Mac / Python)

Si deseas automatizar por carpetas en tu equipo local:
1. Haz doble clic en `Iniciar Compresor.command` (o ejecuta `python3 compresor_pdf.py`).
2. Coloca tus reportes en la carpeta `1_Entrada`.
3. Recibe los archivos optimizados en `2_Comprimidos` y los originales respaldados en `3_Originales_Procesados`.
