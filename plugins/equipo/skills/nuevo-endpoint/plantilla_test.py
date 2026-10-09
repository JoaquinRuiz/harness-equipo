"""Plantilla de tests para un endpoint de TaskFlow.

Copia este fichero a tests/test_<recurso>.py y sustituye lo que va entre <...>.
Las fixtures (client, db, sample_user, sample_project, sample_task, sample_tag) vienen de
tests/conftest.py.
"""


class Test<Recurso><Accion>:
    URL = "/api/<recurso>/{id}/<accion>"

    def test_caso_feliz(self, client, <fixture>):
        resp = client.<metodo>(self.URL.format(id=<fixture>.id), json={<datos_validos>})
        assert resp.status_code == <200_o_201>
        data = resp.get_json()
        assert data["<clave_recurso>"][<campo>] == <valor_esperado>

    def test_no_existe(self, client, db):
        resp = client.<metodo>(self.URL.format(id=9999), json={<datos_validos>})
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_datos_invalidos(self, client, <fixture>):
        resp = client.<metodo>(self.URL.format(id=<fixture>.id), json={<datos_invalidos>})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_conflicto(self, client, <fixture>):
        # Solo si la acción puede chocar con el estado actual del recurso.
        client.<metodo>(self.URL.format(id=<fixture>.id), json={<datos_validos>})
        resp = client.<metodo>(self.URL.format(id=<fixture>.id), json={<datos_validos>})
        assert resp.status_code == 409
        assert set(resp.get_json()) == {"error"}
