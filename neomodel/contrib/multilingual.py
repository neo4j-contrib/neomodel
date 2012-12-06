from .. import RelationshipTo, StructuredNode, StringProperty

class Language(StructuredNode):
    code = StringProperty(unique_index=True)
    name = StringProperty()

class Multilingual(object):
    languages = RelationshipTo("Language", "LANGUAGE")

    def __init__(self, *args, **kwargs):
        try:
            super(Multilingual, self).__init__(*args, **kwargs)
        except TypeError:
            super(Multilingual, self).__init__()

    def attach_language(self, lang):
        self.languages.connect(lang)

    def detach_language(self, lang):
        self.languages.disconnect(lang)

    def has_language(self, lang):
        pass
