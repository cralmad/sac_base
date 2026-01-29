from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuarios(AbstractUser):

    class Meta:
        db_table = 'usuarios'

    def sisvar_payload(self):
        return {
            "id": self.id,
            "nome": self.first_name,
            "username": self.username,
            "permissoes": list(
                self.get_all_permissions()
            )
        }
