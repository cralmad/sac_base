import re

class SchemaValidator:
    def __init__(self, schema):
        self.schema = schema
        self.errors = {}

    def validate(self, data):
        self.errors = {}
        
        for field, rules in self.schema.items():
            value = data.get(field)
            
            # 1. Required
            if rules.get('required') and (value is None or value == ''):
                self._add_error(field, "Este campo é obrigatório")
                continue # Se é obrigatório e não tem, pula as outras validações

            # Se o campo está vazio e não é obrigatório, ignoramos o resto
            if value is None or value == '':
                continue

            # 2. Max Length
            if 'maxlength' in rules and len(str(value)) > rules['maxlength']:
                self._add_error(field, f"Máximo de {rules['maxlength']} caracteres")

            # 3. Min Length
            if 'minlength' in rules and len(str(value)) < rules['minlength']:
                self._add_error(field, f"Mínimo de {rules['minlength']} caracteres")

            # 4. Email Type
            if rules.get('type') == 'email':
                if not re.match(r"[^@]+@[^@]+\.[^@]+", str(value)):
                    self._add_error(field, "E-mail inválido")

            # 5. Booleans (Ex: "ativo")
            if rules.get('type') == 'boolean' and not isinstance(value, bool):
                self._add_error(field, "Valor booleano inválido")

        return len(self.errors) == 0

    def _add_error(self, field, message):
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(message)

    def get_errors(self):
        return self.errors