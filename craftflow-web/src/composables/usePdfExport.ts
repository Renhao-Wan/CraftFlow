import { ref } from 'vue'
import html2pdf from 'html2pdf.js'

/**
 * PDF 导出 composable
 * 将指定 DOM 元素导出为 PDF 文件
 */
export function usePdfExport() {
  const exporting = ref(false)

  /**
   * 导出指定元素为 PDF
   * @param element - 要导出的 DOM 元素
   * @param filename - 文件名（不含 .pdf 后缀）
   */
  async function exportToPdf(element: HTMLElement, filename: string): Promise<void> {
    if (exporting.value) return
    exporting.value = true

    try {
      await html2pdf()
        .set({
          margin: [15, 15, 15, 15],
          filename: `${filename}.pdf`,
          image: { type: 'jpeg', quality: 0.98 },
          html2canvas: { scale: 2, useCORS: true, logging: false },
          jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
          pagebreak: { mode: ['avoid-all', 'css', 'legacy'] },
        })
        .from(element)
        .save()
    } finally {
      exporting.value = false
    }
  }

  return { exporting, exportToPdf }
}
