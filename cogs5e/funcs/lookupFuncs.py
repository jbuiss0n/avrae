"""
Created on Jan 13, 2017

@author: andrew
"""
import copy
import json
import logging

from cogs5e.models.bestiary import Bestiary
from cogs5e.models.errors import NoBestiary
from cogs5e.models.monster import Monster
from cogs5e.models.race import Race
from utils.functions import strict_search, fuzzywuzzy_search_all_3, get_selection, \
    fuzzywuzzy_search_all_3_list, parse_data_entry, search_and_select

log = logging.getLogger(__name__)


class Compendium:
    def __init__(self):
        with open('./res/conditions.json', 'r') as f:
            self.conditions = json.load(f)
        with open('./res/rules.json', 'r') as f:
            self.rules = json.load(f)
        with open('./res/feats.json', 'r') as f:
            self.feats = json.load(f)
        with open('./res/races.json', 'r') as f:
            _raw = json.load(f)
            self.rfeats = []
            self.races = copy.deepcopy(_raw)
            self.fancyraces = [Race.from_data(r) for r in self.races]
            for race in _raw:
                for entry in race['entries']:
                    if isinstance(entry, dict) and 'name' in entry:
                        temp = {'name': "{}: {}".format(race['name'], entry['name']),
                                'text': parse_data_entry(entry['entries']), 'srd': race['srd']}
                        self.rfeats.append(temp)
        with open('./res/classes.json', 'r', encoding='utf-8-sig') as f:
            _raw = json.load(f)
            self.cfeats = []
            self.classes = copy.deepcopy(_raw)
            for _class in _raw:
                for level in _class.get('classFeatures', []):
                    for feature in level:
                        fe = {'name': f"{_class['name']}: {feature['name']}",
                              'text': parse_data_entry(feature['entries']), 'srd': _class['srd']}
                        self.cfeats.append(fe)
                        options = [e for e in feature['entries'] if
                                   isinstance(e, dict) and e['type'] == 'options']
                        for option in options:
                            for opt_entry in option.get('entries', []):
                                fe = {'name': f"{_class['name']}: {feature['name']}: {_resolve_name(opt_entry)}",
                                      'text': f"{_parse_prereqs(opt_entry)}{parse_data_entry(opt_entry['entries'])}",
                                      'srd': _class['srd']}
                                self.cfeats.append(fe)
                for subclass in _class.get('subclasses', []):
                    for level in subclass.get('subclassFeatures', []):
                        for feature in level:
                            options = [f for f in feature.get('entries', []) if
                                       isinstance(f, dict) and f['type'] == 'options']  # battlemaster only
                            for option in options:
                                for opt_entry in option.get('entries', []):
                                    fe = {'name': f"{_class['name']}: {option['name']}: "
                                                  f"{_resolve_name(opt_entry)}",
                                          'text': parse_data_entry(opt_entry['entries']),
                                          'srd': subclass.get('srd', False)}
                                    self.cfeats.append(fe)
                            for entry in feature.get('entries', []):
                                if not isinstance(entry, dict): continue
                                if not entry.get('type') == 'entries': continue
                                fe = {'name': f"{_class['name']}: {subclass['name']}: {entry['name']}",
                                      'text': parse_data_entry(entry['entries']), 'srd': subclass.get('srd', False)}
                                self.cfeats.append(fe)
                                options = [e for e in entry['entries'] if
                                           isinstance(e, dict) and e['type'] == 'options']
                                for option in options:
                                    for opt_entry in option.get('entries', []):
                                        fe = {'name': f"{_class['name']}: {subclass['name']}: {entry['name']}: "
                                                      f"{_resolve_name(opt_entry)}",
                                              'text': parse_data_entry(opt_entry['entries']),
                                              'srd': subclass.get('srd', False)}
                                        self.cfeats.append(fe)
        with open('./res/bestiary.json', 'r') as f:
            self.monsters = json.load(f)
            self.monster_mash = [Monster.from_data(m) for m in self.monsters]
        with open('./res/spells.json', 'r') as f:
            self.spells = json.load(f)
        with open('./res/items.json', 'r') as f:
            _items = json.load(f)
            self.items = [i for i in _items if i.get('type') is not '$']
        with open('./res/auto_spells.json', 'r') as f:
            self.autospells = json.load(f)
        with open('./res/backgrounds.json', 'r') as f:
            self.backgrounds = json.load(f)
        self.subclasses = self.load_subclasses()
        with open('./res/itemprops.json', 'r') as f:
            self.itemprops = json.load(f)

    def load_subclasses(self):
        s = []
        for _class in self.classes:
            subclasses = _class.get('subclasses', [])
            for sc in subclasses:
                sc['name'] = f"{_class['name']}: {sc['name']}"
            s.extend(subclasses)
        return s


def _resolve_name(entry):
    """Resolves the next name of an astranauta entry.
    :param entry (dict) - the entry.
    :returns str - The next found name, or None."""
    if 'entries' in entry and 'name' in entry['entries'][0]:
        return _resolve_name(entry['entries'][0])
    elif 'name' in entry:
        return entry['name']
    else:
        log.warning(f"No name found for {entry}")


def _parse_prereqs(entry):
    if 'prerequisite' in entry:
        return f"*Prerequisite: {entry['prerequisite']}*\n"
    else:
        return ''


c = Compendium()


def searchClass(name):
    return fuzzywuzzy_search_all_3(c.classes, 'name', name)


def searchBackground(name):
    return fuzzywuzzy_search_all_3(c.backgrounds, 'name', name)


# ----- Monster stuff
async def select_monster_full(ctx, name, cutoff=5, return_key=False, pm=False, message=None, list_filter=None,
                              srd=False):
    """
    Gets a Monster from the compendium and active bestiary/ies.
    """
    choices = c.monster_mash.copy()
    try:
        bestiary = Bestiary.from_ctx(ctx)
        choices.extend(bestiary.monsters)
    except NoBestiary:
        pass
    if srd:
        if list_filter:
            old = list_filter
            list_filter = lambda e: old(e) and e.srd
        else:
            list_filter = lambda e: e.srd
        message = "This server only shows results from the 5e SRD."
    return await search_and_select(ctx, choices, name, lambda e: e.name, cutoff, return_key, pm, message, list_filter)


def searchSpell(name):
    return fuzzywuzzy_search_all_3(c.spells, 'name', name, return_key=True)


async def searchSpellNameFull(name, ctx):
    result = searchSpell(name)
    if result is None:
        return None
    strict = result[1]
    results = result[0]
    bot = ctx.bot

    if strict:
        result = results
    else:
        if len(results) == 1:
            result = results[0]
        else:
            result = await get_selection(ctx, [(r, r) for r in results])
            if result is None:
                await bot.send_message(ctx.message.channel, 'Selection timed out or was cancelled.')
                return None
    return result


async def searchCharacterSpellName(name, ctx, char):
    result = fuzzywuzzy_search_all_3_list(char.get_spell_list(), name)
    if result is None:
        return None
    strict = result[1]
    results = result[0]
    bot = ctx.bot

    if strict:
        result = results
    else:
        if len(results) == 1:
            result = results[0]
        else:
            result = await get_selection(ctx, [(r, r) for r in results])
            if result is None:
                await bot.send_message(ctx.message.channel, 'Selection timed out or was cancelled.')
                return None
    return result


def searchAutoSpell(name):
    return fuzzywuzzy_search_all_3(c.autospells, 'name', name)


async def searchAutoSpellFull(name, ctx):
    result = searchAutoSpell(name)
    if result is None:
        return None
    strict = result[1]
    results = result[0]
    bot = ctx.bot

    if strict:
        result = results
    else:
        if len(results) == 1:
            result = results[0]
        else:
            result = await get_selection(ctx, [(r['name'], r) for r in results])
            if result is None:
                await bot.send_message(ctx.message.channel, 'Selection timed out or was cancelled.')
                return None
    return result


def getSpell(spellname):
    return strict_search(c.spells, 'name', spellname)
