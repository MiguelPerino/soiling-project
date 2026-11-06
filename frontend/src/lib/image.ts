/** Redimensiona e comprime a foto NO NAVEGADOR para o tamanho que o modelo do ESP32 espera (lado × lado, esticada,
 *  igual ao treino) e devolve um JPEG. Isso reduz tráfego e memória no ESP32. */
export async function prepareImage(file: Blob, size: number, quality: number): Promise<Blob> {
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" }).catch(() => {
    throw new Error("Não consegui abrir essa imagem. Use JPEG, PNG ou WEBP.");
  });
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Seu navegador não conseguiu preparar a imagem.");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bmp, 0, 0, size, size);
  bmp.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Falha ao comprimir a imagem."))), "image/jpeg", quality / 100),
  );
}
