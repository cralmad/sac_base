from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuarios(AbstractUser):
    nome = models.CharField(max_length=150)

    class Meta:
        db_table = 'usuarios'

    def sisvar_payload(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "permissoes": list(
                self.get_all_permissions()
            )
        }
