from .. import RelationshipTo, StructuredNode, StringProperty
from ..index import NodeIndexManager


class Locale(StructuredNode):
    code = StringProperty(unique_index=True)
    name = StringProperty()

    def __repr__(self):
        return self.code

    def __str__(self):
        return self.code

    @classmethod
    def get(cls, code):
        return Locale.nodes.get(code=code)


class LocalisedIndexManager(NodeIndexManager):
    """ Only return results in current locale """
    def __init__(self, locale_code, *args, **kwargs):
        super(LocalisedIndexManager, self).__init__(*args, **kwargs)
        self.locale_code = locale_code

    def _build_query(self, params):
        q = super(LocalisedIndexManager, self)._build_query(params)
        q += " MATCH (n)-[:LANGUAGE]->(lang:Locale)"
        q += " USING INDEX lang:Locale(code)"
        q += " WHERE lang.code = {_locale_code}"
        params['_locale_code'] = self.locale_code
        return q


class Localised(object):
    locales = RelationshipTo("Locale", "LANGUAGE")

    def __init__(self, *args, **kwargs):
        try:
            super(Localised, self).__init__(*args, **kwargs)
        except TypeError:
            super(Localised, self).__init__()

    def add_locale(self, lang):
        if not isinstance(lang, StructuredNode):
            lang = Locale.get(lang)
        self.locales.connect(lang)

    def remove_locale(self, lang):
        self.locales.disconnect(Locale.get(lang))

    def has_locale(self, lang):
        return self.locales.is_connected(Locale.get(lang))

    @classmethod
    def locale_index(cls, code):
        return LocalisedIndexManager(code, cls, cls.__name__)
