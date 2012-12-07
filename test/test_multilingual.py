from neomodel import StructuredNode, StringProperty
from neomodel.contrib import Multilingual, Language


class Student(Multilingual, StructuredNode):
    name = StringProperty(unique_index=True)


def setup():
    for l in ['fr', 'ar', 'pl', 'es']:
        Language(code=l).save()


def test_multilingual():
    bob = Student(name="Bob", age=77).save()
    bob.attach_language(Language.get("fr"))
    bob.attach_language("ar")
    bob.attach_language(Language.get("ar"))
    bob.attach_language(Language.get("pl"))
    assert bob.has_language("fr")
    assert not bob.has_language("es")
    bob.detach_language("fr")
    assert not bob.has_language("fr")
    assert len(bob.languages) == 2
    assert Language.get("pl") in bob.languages.all()
    assert Language.get("ar") in bob.languages.all()
