from .. import RelationshipTo, StructuredNode, StringProperty


class Language(StructuredNode):
    code = StringProperty(unique_index=True)
    name = StringProperty()

    def __repr__(self):
        return self.code

    def __str__(self):
        return self.code

    _language_cache = {}

    @classmethod
    def get(cls, code):
        if not code in cls._language_cache:
            cls._language_cache[code] = Language.index.get(code=code)
        return cls._language_cache[code]


class Multilingual(object):
    languages = RelationshipTo("Language", "LANGUAGE")

    def __init__(self, *args, **kwargs):
        try:
            super(Multilingual, self).__init__(*args, **kwargs)
        except TypeError:
            super(Multilingual, self).__init__()

    def attach_language(self, lang):
        self.languages.connect(Language.get(lang))

    def detach_language(self, lang):
        self.languages.disconnect(Language.get(lang))

    def has_language(self, lang):
        return self.languages.is_connected(Language.get(lang))
