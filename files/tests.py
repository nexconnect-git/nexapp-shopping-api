import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from files.models import UploadedFile


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    USE_S3=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class UploadedFileApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='uploaduser',
            email='uploaduser@example.com',
            password='pass1234',
            role='admin',
        )
        self.client.force_authenticate(self.user)

    def test_upload_saves_file_locally_and_returns_metadata(self):
        payload = SimpleUploadedFile(
            'hello.txt',
            b'hello from tests',
            content_type='text/plain',
        )

        response = self.client.post(
            reverse('uploaded-file-upload'),
            {
                'file': payload,
                'use_of_image': 'profile_image',
                'client_upload_id': 'upload-test-1',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['original_filename'], 'hello.txt')
        self.assertEqual(response.data['client_upload_id'], 'upload-test-1')
        self.assertEqual(response.data['use_of_image'], 'profile_image')
        self.assertEqual(response.data['content_type'], 'text/plain')
        self.assertEqual(response.data['size'], 16)
        self.assertIn('/media/uploaduser/', response.data['file_url'])
        self.assertIn('/profile_image/', response.data['file_url'])
        uploaded = UploadedFile.objects.get(original_filename='hello.txt')
        self.assertRegex(uploaded.file.name, r'^uploaduser/\d{8}/profile_image/hello\.txt$')

    def test_repeated_client_upload_id_returns_existing_file(self):
        existing = UploadedFile.objects.create(
            client_upload_id='retry-upload-1',
            original_filename='existing.txt',
            file='uploaduser/01012026/general_upload/existing.txt',
            content_type='text/plain',
            size=8,
            uploaded_by=self.user,
        )
        payload = SimpleUploadedFile(
            'hello.txt',
            b'hello from tests',
            content_type='text/plain',
        )

        response = self.client.post(
            reverse('uploaded-file-upload'),
            {'file': payload, 'client_upload_id': 'retry-upload-1'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], str(existing.id))
        self.assertEqual(UploadedFile.objects.filter(client_upload_id='retry-upload-1').count(), 1)

    def test_rejects_empty_upload(self):
        payload = SimpleUploadedFile('empty.txt', b'', content_type='text/plain')

        response = self.client.post(
            reverse('uploaded-file-upload'),
            {'file': payload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('file', response.data)

    def test_rejects_invalid_use_of_image(self):
        payload = SimpleUploadedFile(
            'hello.txt',
            b'hello from tests',
            content_type='text/plain',
        )

        response = self.client.post(
            reverse('uploaded-file-upload'),
            {'file': payload, 'use_of_image': 'not_real'},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('use_of_image', response.data)
