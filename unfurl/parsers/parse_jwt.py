# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import logging

log = logging.getLogger(__name__)

jwt_edge = {
    'color': {
        'color': '#D038F6'
    },
    'title': 'JSON Web Token',
    'label': 'JWT'
}

jwt_fields = {
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.1
    'iss': {
        'name': 'Issuer',
        'value': 'The "iss" (issuer) claim identifies the principal that issued the JWT.',
        'hover': 'This is a "Registered Claim Name" per RFC 7519. The processing <br>'
                 'of this claim is generally application specific. The "iss" value is a <br>'
                 'case-sensitive string containing a StringOrURI value.<br>'
                 'Use of this claim is OPTIONAL. '
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.2
    'sub': {
        'name': 'Subject',
        'value': 'The "sub" (subject) claim identifies the principal that is the subject of the JWT.',
        'hover': 'This is a "Registered Claim Name" per RFC 7519. The claims in a JWT are '
                 'normally statements about the subject.  The subject value MUST either be '
                 'scoped to be locally unique in the context of the issuer or be globally unique. '
                 'The processing of this claim is generally application specific. The "sub" '
                 'value is a case-sensitive string containing a StringOrURI value. '
                 'Use of this claim is OPTIONAL.'
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.3
    'aud': {
        'name': 'Audience',
        'value': 'The "aud" (audience) claim identifies the recipients that the JWT is intended for.',
        'hover': 'Each principal intended to process the JWT MUST identify itself with a value in the audience claim. '
                 'If the principal processing the claim does not identify itself with a value in the "aud" claim when '
                 'this claim is present, then the JWT MUST be rejected. In the general case, the "aud" value is an '
                 'array of case- sensitive strings, each containing a StringOrURI value. In the special case when the '
                 'JWT has one audience, the "aud" value MAY be a single case-sensitive string containing a '
                 'StringOrURI value. The interpretation of audience values is generally application specific. Use of '
                 'this claim is OPTIONAL. '
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.4
    'exp': {
        'name': 'Expiration Time',
        'value': 'The "exp" (expiration time) claim identifies the expiration time on or after which the JWT MUST NOT '
                 'be accepted for processing.',
        'hover': 'The processing of the "exp" claim requires that the current date/time MUST be before the expiration '
                 'date/time listed in the "exp" claim. Implementers MAY provide for some small leeway, usually no '
                 'more than a few minutes, to account for clock skew. Its value MUST be a number containing a '
                 'NumericDate value. Use of this claim is OPTIONAL. '
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.5
    'nbf': {
        'name': 'Not Before',
        'value': 'The "nbf" (not before) claim identifies the time before which the JWT MUST NOT be accepted for '
                 'processing.',
        'hover': 'The processing of the "nbf" claim requires that the current date/time MUST be after or equal to the '
                 'not-before date/time listed in the "nbf" claim. Implementers MAY provide for some small leeway, '
                 'usually no more than a few minutes, to account for clock skew. Its value MUST be a number '
                 'containing a NumericDate value. Use of this claim is OPTIONAL. '
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.6
    'iat': {
        'name': 'Issued At',
        'value': 'The "iat" (issued at) claim identifies the time at which the JWT was issued.',
        'hover': 'This claim can be used to determine the age of the JWT. Its value MUST be a number containing a '
                 'NumericDate value. Use of this claim is OPTIONAL. '
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.7
    'jti': {
        'name': 'JWT ID',
        'value': 'The "jti" (JWT ID) claim provides a unique identifier for the JWT.',
        'hover': 'The identifier value MUST be assigned in a manner that ensures that there is a negligible '
                 'probability that the same value will be accidentally assigned to a different data object; if the '
                 'application uses multiple issuers, collisions MUST be prevented among values produced by different '
                 'issuers as well. The "jti" claim can be used to prevent the JWT from being replayed. The "jti" '
                 'value is a case-sensitive string. Use of this claim is OPTIONAL. '
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-5.1
    'typ': {
        'name': 'Type',
        'value': 'The "typ" (type) Header Parameter is used to declare the media type of this complete JWT.',
        'hover': 'This is intended for use by the JWT application when values that are not JWTs could also be present '
                 'in an application data structure that can contain a JWT object '
    },
    # ref: https://datatracker.ietf.org/doc/html/rfc7519#section-5.2
    'cty': {
        'name': 'Content Type',
        'value': 'The "cty" (content type) Header Parameter is used to convey structural information about the JWT.',
        'hover': 'In the case that nested signing or encryption is employed, this Header Parameter MUST be present; '
                 'in this case, the value MUST be "JWT", to indicate that a Nested JWT is carried in this JWT. '
    },
    'alg': {
        'name': 'Algorithm',
        'value': 'The "alg" (algorithm) Header Parameter identifies the cryptographic algorithm used.',
        'hover': 'The issuer can freely set an algorithm to verify the signature on the token. However, '
                 'some supported algorithms are insecure. '
    },
    'kid': {
        'name': 'Key ID',
        'value': 'The "kid" (key ID) Header Parameter is a hint indicating which key was used to generate the token '
                 'signature.',
        'hover': 'The server will match this value to a key on file in order to verify that the signature is valid '
                 'and the token is authentic. '
    },
    'x5c': {
        'name': 'x.509 Certificate Chain',
        'value': 'x.509 Certificate Chain',
        'hover': 'A certificate chain in RFC4945 format corresponding to the private key used to generate the token '
                 'signature. The server will use this information to verify that the signature is valid and the token '
                 'is authentic. '
    },
    'x5u': {
        'name': 'x.509 Certificate Chain URL',
        'value': 'x.509 Certificate Chain URL',
        'hover': 'A URL where the server can retrieve a certificate chain corresponding to the private key used to '
                 'generate the token signature. The server will retrieve and use this information to verify that the '
                 'signature is authentic. '
    },
    'enc': {
        'name': 'Encryption Algorithm',
        'value': 'The "enc" (Encryption Algorithm) Header Parameter identifies the encryption algorithm used.',
        'hover': None
    },
}


def run(unfurl, node):

    if node.key in jwt_fields.keys():
        # Ensure a predecessor node was an encoded JWT node, so we don't apply the JWT
        # field descriptions to a random thing that happens to share their names.
        predecessor_chain = unfurl.get_predecessor_chain(node)
        if not unfurl.check_if_in_node_chain(predecessor_chain, 'data_type', ('jwt.header.enc', 'jwt.payload.enc'), 1):
            return

        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=jwt_fields[node.key]['value'], parent_id=node.node_id,
            hover=jwt_fields[node.key]['hover'],
            incoming_edge_config=jwt_edge)

        return

    if not isinstance(node.value, str):
        return

    jwt_re = re.compile(r'^(?P<jwt_header_enc>[A-Za-z0-9_\-]{8,})\.'
                        r'(?P<jwt_payload_enc>[A-Za-z0-9_\-]{8,})\.'
                        r'(?P<jwt_sig_enc>[A-Za-z0-9_\-]{8,})$')
    m = jwt_re.match(node.value)
    if m:
        if m.groupdict().get('jwt_header_enc'):
            unfurl.add_to_queue(
                data_type='jwt.header.enc', key='JWT Header', value=m['jwt_header_enc'],
                hover='JSON Web Tokens (JWTs) have three distinct parts: the header, payload, and signature. '
                      'The <b>header</b> identifies which algorithm is used to generate the signature.',
                parent_id=node.node_id, incoming_edge_config=jwt_edge)

        if m.groupdict().get('jwt_payload_enc'):
            unfurl.add_to_queue(
                data_type='jwt.payload.enc', key='JWT Payload', value=m['jwt_payload_enc'], parent_id=node.node_id,
                hover='JSON Web Tokens (JWTs) have three distinct parts: the header, payload, and signature. '
                      'The <b>payload</b> contains a set of claims, which can be either standard or custom.',
                incoming_edge_config=jwt_edge)

        if m.groupdict().get('jwt_sig_enc'):
            unfurl.add_to_queue(
                data_type='jwt.sig.enc', key='JWT Signature', value=m['jwt_sig_enc'], parent_id=node.node_id,
                hover='JSON Web Tokens (JWTs) have three distinct parts: the header, payload, and signature. '
                      'The <b>signature</b> validates the token; it is calculated by passing the encoded header '
                      'and payload through the cryptographic algorithm specified in the header.',
                incoming_edge_config=jwt_edge)
