import os
import asyncio
import uuid
import cloudinary
import cloudinary.uploader
from app.core.config import settings


class StorageService:
    def __init__(self):
        self.is_cloudinary_configured = False

        cloudinary_url = getattr(settings, "CLOUDINARY_URL", os.getenv("CLOUDINARY_URL"))
        if cloudinary_url:
            from urllib.parse import urlparse
            try:
                cloudinary_url = cloudinary_url.strip().strip('"').strip("'")
                parsed = urlparse(cloudinary_url)
                cloud_name = parsed.hostname
                api_key = parsed.username
                api_secret = parsed.password

                if cloud_name and api_key and api_secret:
                    cloudinary.config(
                        cloud_name=cloud_name,
                        api_key=api_key,
                        api_secret=api_secret,
                        secure=True,
                    )
                    self.is_cloudinary_configured = True
                    print("[CLOUDINARY] Configuré avec succès via CLOUDINARY_URL.")
            except Exception as e:
                print(f"[CLOUDINARY] Erreur lors de l'initialisation depuis CLOUDINARY_URL: {e}")

        if not self.is_cloudinary_configured:
            cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", os.getenv("CLOUDINARY_CLOUD_NAME"))
            api_key = getattr(settings, "CLOUDINARY_API_KEY", os.getenv("CLOUDINARY_API_KEY"))
            api_secret = getattr(settings, "CLOUDINARY_API_SECRET", os.getenv("CLOUDINARY_API_SECRET"))

            if cloud_name and api_key and api_secret:
                cloud_name = str(cloud_name).strip().strip('"').strip("'")
                api_key = str(api_key).strip().strip('"').strip("'")
                api_secret = str(api_secret).strip().strip('"').strip("'")

                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    secure=True,
                )
                self.is_cloudinary_configured = True
                print("[CLOUDINARY] Configuré avec succès via les paramètres individuels.")

    async def _upload_bytes(self, content: bytes, folder: str, resource_type: str = "auto", filename: str = "upload") -> str:
        if not self.is_cloudinary_configured:
            unique_name = f"{folder}/{uuid.uuid4().hex}.{filename.split('.')[-1] if '.' in filename else 'bin'}"
            print(f"[MOCK CLOUDINARY] Fichier {filename} intercepté (Cloudinary non configuré). URL générée -> {unique_name}")
            return f"https://res.cloudinary.com/mock_cloud/image/upload/{unique_name}"

        try:
            upload_result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                content,
                folder=folder,
                resource_type=resource_type,
            )
            url = upload_result.get("secure_url") or upload_result.get("url") or ""
            print(f"[CLOUDINARY] Upload réussi -> {url}")
            return url
        except Exception as e:
            print(f"Erreur de téléversement Cloudinary: {e}")
            return ""

    async def upload_file(self, file_obj, folder: str = "uploads", resource_type: str = "auto") -> str:
        if not file_obj:
            return ""

        filename = getattr(file_obj, "filename", "") or "upload"
        content = await file_obj.read()
        await file_obj.seek(0)
        return await self._upload_bytes(content, folder=folder, resource_type=resource_type, filename=filename)

    async def upload_document_cover(self, file_obj, folder: str = "library") -> str:
        if not file_obj:
            return ""

        filename = getattr(file_obj, "filename", "") or "document"
        content_type = getattr(file_obj, "content_type", "") or ""
        ext = filename.split('.')[-1].lower() if '.' in filename else ""
        is_image = content_type.startswith("image/") or ext in {"png", "jpg", "jpeg", "webp", "gif", "svg", "bmp"}

        if is_image:
            return await self.upload_file(file_obj, folder=folder, resource_type="image")

        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='1600'>
  <rect width='100%' height='100%' fill='#0f172a'/>
  <rect x='80' y='80' width='1040' height='1440' rx='32' fill='#111827'/>
  <rect x='140' y='220' width='920' height='140' rx='18' fill='#1f2937'/>
  <rect x='140' y='400' width='760' height='24' rx='12' fill='#374151'/>
  <rect x='140' y='452' width='640' height='24' rx='12' fill='#374151'/>
  <rect x='140' y='520' width='540' height='24' rx='12' fill='#374151'/>
  <path d='M760 1160c0-95 77-172 172-172h48v160h-48c-46 0-84 38-84 84v96H760z' fill='#38bdf8'/>
  <circle cx='900' cy='1080' r='120' fill='#f8fafc' opacity='0.9'/>
  <text x='600' y='1360' text-anchor='middle' font-size='64' font-family='Arial, sans-serif' fill='#f8fafc'>Document LeRéseau</text>
</svg>"""
        return await self._upload_bytes(svg.encode("utf-8"), folder=folder, resource_type="image", filename="document-cover.svg")


storage = StorageService()
