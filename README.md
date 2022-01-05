# Constituency Tree Service

Transforms `iol:Sentence`s into constituency trees using CoreNLP.

## Model

Every node is a `nif:String` has the following properties:

- `nif:isString`: The string this node (and it's children) represent.
- `nif:posTag`: The OLiA tag for this node.
- `nif:subString`: Points to the child nodes of this node.
- `nif:superString`: Points to the parent node of this node.
- `nif:beginIndex`: The index in the superstring where this node begins (inclusive).
- `nif:endIndex`: The index in the superstring where this node ends (inclusive).

## Config

- `NODE_URI_BASE`: Base URI for new Nodes.
- `CORENLP_URL`: The URL where the CoreNLP server is accessible.
