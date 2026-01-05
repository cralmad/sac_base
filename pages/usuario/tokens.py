from rest_framework_simplejwt.tokens import RefreshToken

class CustomRefreshToken(RefreshToken):

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)

        token["id"] = user.id
        token["username"] = user.username
        token["email"] = user.email
        token["permissoes"] = list(user.get_all_permissions())

        return token
