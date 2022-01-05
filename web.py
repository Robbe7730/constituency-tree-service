import uuid
import os

from nltk.parse.corenlp import CoreNLPParser, CoreNLPServer
from nltk import word_tokenize
import nltk
nltk.download('punkt')

from flask import Response, request

from collections import namedtuple

from helpers import logger

from rdflib import Graph, URIRef, Literal, Namespace, RDF, ConjunctiveGraph, BNode

NIF = Namespace("http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#")
OLIA = Namespace("http://purl.org/olia/olia.owl#")
MU = Namespace("http://mu.semte.ch/vocabularies/core/")

NODE_URI_BASE = os.environ["NODE_URI_BASE"]
CORENLP_URL = os.environ["CORENLP_URL"]
MU_SPARQL_ENDPOINT = os.environ["MU_SPARQL_ENDPOINT"]
MU_APPLICATION_GRAPH = os.environ["MU_APPLICATION_GRAPH"]

parser = CoreNLPParser(url=CORENLP_URL)

@app.route("/.mu/delta", methods=["POST"])
def delta():
    logger.debug(f"Got delta with data {request.data}")

    data = request.json

    if not data:
        return Response("Invalid data", 400)

    sentence_uris = []
    values = {}

    for delta in data:
        for tup in delta["inserts"]:
            if tup["predicate"]["value"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" and tup["object"]["value"] == "http://www.ontologydesignpatterns.org/ont/dul/IOLite.owl#Sentence":
                sentence_uris.append(tup["subject"]["value"])
            if tup["predicate"]["value"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#value":
                values[tup["subject"]["value"]] = tup["object"]["value"].encode().decode('unicode-escape')

    # TODO: Here, we could check if a URI has a value/type in the database that's not in the delta
    # TODO: Check if we have already processed this sentence

    logger.debug(f"Found {len(sentence_uris)} iol:Sentence and {len(values)} rdf:value")

    if len(sentence_uris) == 0:
        return Response("No iol:Sentence found", 200)

    for uri in sentence_uris:
        if uri not in values:
            logger.error(f"No value found for {uri}")
            continue

        process_sentence(values[uri], URIRef(uri))

    return Response("OK", 200)

def process_sentence(sentence, sentence_uuid):
    try:
        tree = next(parser.parse(word_tokenize(sentence)))[0]
        graph = ConjunctiveGraph('SPARQLUpdateStore', identifier=MU_APPLICATION_GRAPH)
        graph.open((MU_SPARQL_ENDPOINT, MU_SPARQL_ENDPOINT))
        process_constituency_tree(tree, sentence, graph, sentence_uuid)
    except Exception as e:
        logger.error(e)
        raise e

ProcessResult = namedtuple("ProcessResult", "match_len uri")

olia_type = {
    # Based on https://www.ibm.com/docs/en/wca/3.5.0?topic=analytics-part-speech-tag-sets
    "DT": OLIA.Determiner,
    "QT": OLIA.Quantifier,
    "CD": OLIA.CardinalNumber,
    "NN": OLIA.Noun,
    "NNS": OLIA.Noun, # plural
    "NNP": OLIA.ProperNoun,
    "NNPS": OLIA.ProperNoun, # plural
    "EX": OLIA.ExistentialParticle,
    "PRP": OLIA.PersonalPronoun,
    "PRP$": OLIA.PossessivePronoun,
    "POS": OLIA.PossessionMarker, # TODO: Not sure if this is right...
    "RBS": OLIA.Adverb, # superlative
    "RBR": OLIA.Adverb, # comparative
    "RB": OLIA.Adverb,
    "JJS": OLIA.Adjective, # superlative
    "JJR": OLIA.Adjective, # comparative
    "JJ": OLIA.Adjective,
    "MD": OLIA.ModalVerb,
    "VB": OLIA.Verb,
    "VBP": OLIA.Verb, # present tense, other than third person singular
    "VBZ": OLIA.Verb, # present tense, third person singular
    "VBD": OLIA.Verb, # past tense
    "VBN": OLIA.Verb, # past participle
    "VBG": OLIA.Verb, # gerund or present participle
    "WDT": OLIA.InterrogativeDeterminer,
    "WP": OLIA.RelativeDeterminer,
    "WP$": OLIA.WHDeterminer, # WHDeterminer is deprecated, but I don't know which of the alternatives match here
    "WRB": OLIA.WHTypeAdverbs,
    "TO": OLIA.Preposition, # specifically "to"
    "IN": OLIA.Preposition, # or OLIA.SubordinatingConjunction?
    "CC": OLIA.CoordinatingConjunction,
    "UH": OLIA.Interjection,
    "RP": OLIA.Particle,
    "SYM": OLIA.Symbol,
    "$": OLIA.Symbol, # specifically for currency
    "\"": OLIA.Quote,
    "''": OLIA.Quote,
    "(": OLIA.OpenBracket,
    ")": OLIA.CloseBracket,
    ",": OLIA.Comma,
    ".": OLIA.SentenceFinalPunctuation,
    ":": OLIA.SentenceMedialPunctuation,

    # TODO: find an exhaustive list of these abbreviations
    # http://surdeanu.cs.arizona.edu//mihai/teaching/ista555-fall13/readings/PennTreebankConstituents.html
    "S": OLIA.Sentence,
    "NP": OLIA.NounPhrase,
    "VP": OLIA.VerbPhrase,
    "PP": OLIA.PrepositionalPhrase,
    "ADVP": OLIA.AdverbPhrase,
    "SBAR": OLIA.Sentence,
    "ADJP": OLIA.AdjectivePhrase,
    "NML": OLIA.NounPhrase,
    "WHNP": OLIA.WHNounPhrase,
    "WHADVP": OLIA.WHAdverbPhrase,
    "WHADJP": OLIA.WHAdjectivePhrase,
    "WHPP": OLIA.WHPrepositionalPhrase,
    "SQ": OLIA.Question,
    "SBARQ": OLIA.Question,
    "INTJ": OLIA.Interjection,
    "FRAG": OLIA.Fragment,
}

def insert_olia_type(uri, label, graph):
    # Remove suffixes like -TMP
    label_base = label.split("-")[0]
    try:
        graph.add((uri, NIF.posTag, olia_type[label_base]))
    except KeyError as e:
        raise Exception(f"No OLiA tag for label '{label}'.") from e

def process_constituency_tree(node, text, graph, node_uri=None):
    if node_uri is None:
        node_uuid = str(uuid.uuid4()).replace("-", "").upper()
        node_uri = URIRef(NODE_URI_BASE + node_uuid)
        # Insert rdf:type first so mu-auth can recognize it as an allowed type
        graph.add((node_uri, RDF.type,     NIF.String))
        graph.add((node_uri, MU.uuid,      Literal(node_uuid)))
    else:
        graph.add((node_uri, RDF.type,     NIF.String))

    if len(node) == 1 and type(node[0]) == str:
        value = node[0]
    else:
        curr_i = 0
        for child in node:
            while text[curr_i].isspace():
                curr_i += 1
            result = process_constituency_tree(child, text[curr_i:], graph)

            graph.add((result.uri, NIF.beginIndex,  Literal(curr_i)))
            graph.add((result.uri, NIF.endIndex,    Literal(curr_i + result.match_len - 1)))
            graph.add((node_uri,   NIF.subString,   result.uri))
            graph.add((result.uri, NIF.superString, node_uri))

            curr_i += result.match_len
        value = text[:curr_i]

    graph.add((node_uri, NIF.isString, Literal(value)))
    insert_olia_type(node_uri, node.label(), graph)

    return ProcessResult(match_len=len(value), uri=node_uri)
