import os
import asyncio
import uuid
import cloudinary
import cloudinary.uploader
from app.core.config import settings

class StorageService:
    def __init__(self):
        # We check if Cloudinary is configured via separate settings or a CLOUDINARY_URL string
        self.is_cloudinary_configured = False
        
        # Priority 1: CLOUDINARY_URL connection string
        cloudinary_url = getattr(settings, "CLOUDINARY_URL", os.getenv("CLOUDINARY_URL"))
        if cloudinary_url:
            from urllib.parse import urlparse
            try:
                # Strip spaces or quotes if any
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
                        secure=True
                    )
                    self.is_cloudinary_configured = True
                    print("[CLOUDINARY] Configuré avec succès via CLOUDINARY_URL.")
            except Exception as e:
                print(f"[CLOUDINARY] Erreur lors de l'initialisation depuis CLOUDINARY_URL: {e}")
        
        # Priority 2: Individual configuration parameters (fallback if URL parsing did not configure it)
        if not self.is_cloudinary_configured:
            cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", os.getenv("CLOUDINARY_CLOUD_NAME"))
            api_key = getattr(settings, "CLOUDINARY_API_KEY", os.getenv("CLOUDINARY_API_KEY"))
            api_secret = getattr(settings, "CLOUDINARY_API_SECRET", os.getenv("CLOUDINARY_API_SECRET"))
            
            if cloud_name and api_key and api_secret:
                # Strip spaces or quotes
                cloud_name = str(cloud_name).strip().strip('"').strip("'")
                api_key = str(api_key).strip().strip('"').strip("'")
                api_secret = str(api_secret).strip().strip('"').strip("'")
                
                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    secure=True
                )
                self.is_cloudinary_configured = True
                print("[CLOUDINARY] Configuré avec succès via les paramètres individuels.")

    async def upload_file(self, file_obj, folder: str = "uploads") -> str:
        """
        Uploads a file to Cloudinary (or generates a Mock URL if not configured) and returns the public URL.
        Supports images, videos, and documents (like PDFs).
        """
        if not file_obj:
            return ""

        ext = file_obj.filename.split('.')[-1] if (file_obj.filename and '.' in file_obj.filename) else 'bin'
        unique_name = f"{folder}/{uuid.uuid4().hex}.{ext}"

        if not self.is_cloudinary_configured:
            print(f"[MOCK CLOUDINARY] Fichier {file_obj.filename} intercepté (Cloudinary non configuré). URL générée -> {unique_name}")
            return f"https://res.cloudinary.com/mock_cloud/image/upload/{unique_name}"

        try:
            content = await file_obj.read()
            # Reset cursor position so the file object can be read again elsewhere if needed
            await file_obj.seek(0)

            # Upload to Cloudinary using a thread pool to avoid blocking the async event loop
            upload_result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                content,
                folder=folder,
                resource_type="auto"
            )
            
            # Retrieve the secure URL
            url = upload_result.get("secure_url") or upload_result.get("url") or ""
            print(f"[CLOUDINARY] Fichier {file_obj.filename} téléversé avec succès -> {url}")
            return url
        except Exception as e:
            print(f"Erreur de téléversement Cloudinary: {e}")
            return ""

storage = StorageService()
