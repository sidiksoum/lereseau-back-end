import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from app.core.config import settings
import uuid

class StorageService:
    def __init__(self):
        self.bucket = getattr(settings, "AWS_S3_BUCKET_NAME", os.getenv("AWS_S3_BUCKET_NAME", "lereseau-premium-docs"))
        self.region = getattr(settings, "AWS_REGION", os.getenv("AWS_REGION", "eu-west-3"))
        
        aws_access_key = getattr(settings, "AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", "mock_access"))
        aws_secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", "mock_secret"))
        
        self.is_mocked = (aws_access_key == "mock_access" or not aws_access_key)
        
        if not self.is_mocked:
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
        else:
            self.s3_client = None

    async def upload_file(self, file_obj, folder: str = "uploads") -> str:
        """
        Uploads a file to AWS S3 (or generates a Mock URL) and returns the public URL.
        """
        ext = file_obj.filename.split('.')[-1] if (file_obj.filename and '.' in file_obj.filename) else 'bin'
        unique_name = f"{folder}/{uuid.uuid4().hex}.{ext}"
        
        if self.is_mocked:
            print(f"[MOCK S3] Fichier {file_obj.filename} intercepté. (Sauvegarde AWS simulée) -> {unique_name}")
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{unique_name}"
        
        try:
            content = await file_obj.read()
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=unique_name,
                Body=content,
                ContentType=file_obj.content_type
            )
            await file_obj.seek(0)
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{unique_name}"
        except ClientError as e:
            print(f"Erreur Amazon S3: {e}")
            return ""
        except NoCredentialsError:
            print("Credentials AWS introuvables.")
            return ""

storage = StorageService()
