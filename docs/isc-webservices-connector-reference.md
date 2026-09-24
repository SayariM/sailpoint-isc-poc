# ISC Web Services Connector — configuration reference

Condensed from SailPoint Identity Security Cloud connector documentation
(documentation.sailpoint.com/connectors/webservices/, revised 04 September 2026).
Source links are given per section.

## What it is

A generic connector for any managed system reachable over web services. It reads
and writes using that system's own API. Both JSON and XML are supported for read
and write.
Source: /integrating_webservices/introduction.html

WARNING — never hard-code sensitive data in source configuration. Hard-coded
secrets leak when the configuration is promoted to production. Put secrets in the
encrypted attribute value list in the application XML and reference the variable
name instead, e.g.
`<entry key="encrypted" value="accesstoken, refresh_token, Custom_Variable"/>`
Source: /integrating_webservices/introduction.html

## Supported HTTP operations

Test Connection, Account Aggregation, Account Delta Aggregation, Group
Aggregation, Resource Aggregation - {resourceName}, Get Object, Get Object-Group,
Create Account, Update Account, Delete Account, Enable Account, Disable Account,
Unlock Account, Change Password, Add Entitlement, Remove Entitlement,
Pass-through Authentication, Custom Authentication, Get Partitions, Partitioned
Account Aggregation.

Notes that matter during design:

- **Delete Account is only reachable through a Before Provisioning rule** — the
  rule rewrites the plan's account operation from disable to delete.
- **Entitlement aggregation schema must be configured manually via the SailPoint
  APIs**; it cannot be done in the UI. SailPoint Support or Expert Services
  involvement is expected.
- Native identity in the provisioning plan is referenced as `$plan.planNativeIdentity$`.
- External DTD access is disabled during XML parsing.
- Cookies are supported by default and shared across endpoints within the same
  operation; disable with the `disableCookies` attribute set to `true`
  (not applicable to the authentication call).

Source: /integrating_webservices/http_operations.html

## Authentication

Types: Basic, API Token, OAuth 2.0, Custom Authentication, plus client
certificate (mutual TLS) as a common setting.

### API Token
Stored in the `accesstoken` application attribute. Format is `token_type API_token`,
e.g. `Bearer ********`. If the token type is omitted the connector uses `Bearer`.
Referenced anywhere via the placeholder `$application.accesstoken$` — usable in
request URL, HTTP headers and request body. Multiple token placeholders can be
defined.
Source: /integrating_webservices/api_token_authentication.html

### OAuth 2.0
Common fields: Base URL, Token URL, OAuth Headers, OAuth Headers to Exclude,
OAuth Request Parameters, OAuth Body Attributes to Exclude.

Grant types: Password, Client Credentials, Refresh Token, JWT Bearer Token,
SAML Bearer Assertion.

Details worth knowing:

- The token URL supports attribute replacement, e.g. `$application.client_secret$`.
- By default an `Authorization: BASIC` header carrying base64 client_id:client_secret
  is included in the token request. Targets that reject it need it listed in
  **OAuth Headers to Exclude**.
- Content-Type for OAuth 2.0 can only be `application/x-www-form-urlencoded`. If the
  target demands a different content type, use **Custom Authentication** instead.

Source: /integrating_webservices/oauth_2.0_authentication.html

## Operation configuration

### General information
- **Operation Name** must be unique. Renaming an existing operation breaks
  configured endpoint and parent-child relationships, which must then be rebuilt.
- **Operation Type** selects from the supported operation list.
- **Use cURL Command** lets you paste a full cURL string instead of specifying
  Context URL and HTTP Method separately.
- **Context URL** is appended to the source Base URL, e.g. `/2/team/members/list`.
  It may be empty. Keywords usable with the `$` placeholder: `plan`, `response`,
  `application`, `getobject`, `authenticate`.
- **HTTP Method**: GET, PUT, POST, DELETE, PATCH.
- Special characters in the context URL — commas, parentheses, brackets, braces,
  pound signs — may require disabling the `skipEncodingDecodingUrl` key.
- Expression language is supported in URLs when wrapped in `_#` … `_#`, over the
  Response, Plan and Application objects.

Source: /integrating_webservices/general_information.html

### Response information
- **Root Path** is the common path shared by every attribute in the response
  mapping for that operation. Default is `$`.
  JSON example: `$.members.profile`
  XML example: `//wd:Response_Data/wd:Worker/wd:Worker_Data`
- **Success Code** accepts HTTP status codes in CSV form, e.g. `200, 201, 203`.
  If empty, 200–299 are accepted. `2**` is also valid.
- A null HTTP response body with custom error messages is supported, and
  pagination works with a null root path.

Source: /integrating_webservices/response_information.html

### Response mapping
Maps each **Schema Attribute** to an **Attribute Path** (JSONPath or XPath). The
root path is automatically prefixed to the attribute path.
JSON: root `$.members.profile` + attribute `member_id` → `$.members.profile.member_id`
XML: root `//wd:Response_Data/wd:Worker/wd:Worker_Data` + `sf:FirstName`
Schema attributes must be added manually for the target system.
Source: /integrating_webservices/response_mapping.html

## Paging

Three mechanisms: limit-offset, response markers, and response header links.
Configured on the Paging tab of aggregation operations.

Rules:
- Every paging configuration step starts on a new line.
- Put a space after every operator, condition and placeholder.
- Values resolve through placeholder notation `$response.attribute_key$`.
- Intermediate values can be carried between page requests by using any attribute
  key that is not a reserved keyword.
- Parentheses group complex conditions, e.g.
  `TERMINATE_IF ($someattribute$ == TRUE) && ($otherattribute$ == NULL)`

Keywords: `application` (baseUrl), `endpoint` (relativeURL, fullUrl), `limit`,
`offset`, `request`, `requestHeaders`, `response`, `responseHeaders`,
`TERMINATE_IF` (with `NO_RECORDS`, `RECORDS_COUNT`), `NULL`, `REMOVE`.

Operators: arithmetic and logical `+ - * / = && ||`; conditional
`< > <= >= == !=`. Avoid arithmetic inside `TERMINATE_IF` — compute first, then test.

Source: /integrating_webservices/paging_tab.html, /pagination.html, /http_paging.html

## Delta aggregation and common configuration

- **Enable Delta Aggregation** aggregates only accounts changed since the last run.
  Only works if the managed system itself supports delta.
- **Account Delete Status Attribute** marks objects deleted during delta runs,
  e.g. `deleted=true`.
- **Connection Timeout (seconds)**.
- **Client Certificate / Client Private Key** — PEM format only, and the private
  key must be an **RSA** PEM key. Convert with
  `openssl rsa -in key.key -out rsa_private_key.pem`. Generating keys with openSSL
  on the VA itself is discouraged; the resulting signature is not accepted.
- **Account Enable Status Attribute**, e.g. `status=Active`. Accounts matching are
  Enabled, all others Disabled. Multiple values are comma-separated
  (`status=Active,Pending`). Limitations: conditional operators are **not**
  supported (`||`, `&&`), and selecting the n-th element of a list is not
  supported (e.g. `values[?(@.name=="accountDisabled")].values[0]`). Use a
  Web Services After Operation Rule for those cases.
- **Account Lock Status Attribute**, e.g. `status=Locked,Inactive`. Locked accounts
  are excluded from provisioning.
- **Use hasMore Attribute for Aggregation Termination** — terminates aggregation
  based on a `hasMore` boolean set in the `transientValues` map by a
  Before/After Operation rule.

Source: /integrating_webservices/delta_aggregation_settings_and_common_configuration.html

## Additional settings

Provisioning settings:
- **Create Account With "Ent" Request** — create executes with entitlement
  attributes; the account link appears if the response carries the identity attribute.
- **Throw Provisioning Rules** — surface exceptions from
  WebServicesBeforeOperationRule, WebServicesAfterOperationRule, or both.
- **Update Attributes with Change Password** — combines password and attribute
  change in one request; add/remove entitlement requests still run independently.
- **Get Object Required for PTA** — runs Get Object during pass-through
  authentication to verify the user exists.

Error handling:
- **HTTP Errors** — key/value pairs for error codes and messages the API may
  return. Critical case: an API that returns HTTP `200` while the payload contains
  an error. Without a configured HTTP error the connector treats it as success.
- **Object Not Found**, **Authentication Failed** and **Expired Password** error
  messages are configured as strings.
- With OAuth 2.0, correctly configured expiry messages let the connector refresh
  the access token after the first failed attempt and retry.
- **Disable Cookies** for all operations except authentication.
- **retryableErrors** can be set through the REST API:
  `[{"op":"add","path":"connectorAttributes/retryableErrors","value":["<Error 1>","<Error 2>"]}]`
  Errors in `possibleHttpErrors` are not retried.

Source: /integrating_webservices/additional_settings.html

## Partitioning

Parallel aggregation with a configurable thread count. Requires a **Partitioned
Account Aggregation** operation; dynamic partitioning also requires a
**Get Partitions** operation.
Source: /integrating_webservices/partitioning_settings.html, /general_information.html

## Known failure modes (troubleshooting index)

Endpoint not found in namespace; RateLimit headers not received; test connection
failure on TLS 1.0 / WebSphere; aggregation error when a JSON attribute name
contains a period; provisioning error when the request body has a multivalued
attribute with quotation marks; create account failure when using recommended
mappings in the account policy; HTTP 429 and HTTP 500 aggregation failures;
illegal character during test connection; aggregation failure when the context
URL contains special characters; SOAP body trimmed when the XML request body
contains `$`; Oracle HCM accounts deleted during full aggregation; HTTP 401
invalid or missing credentials; operations failing from a missing cookie; account
enable field not honoured when set by an afterOperation rule; Qualys DTD response
parse failure.
Source: /integrating_webservices/troubleshooting.html

## Onboarding implications

- Ask for a **sample response payload** early. Root path, response mapping and
  paging config are all derived from it.
- Confirm **every returned resource carries a unique id**. Connectors build their
  internal object from an id field; a resource list without one fails at the first
  record.
- Ask explicitly whether the API ever returns **HTTP 200 with an error body** —
  that determines whether HTTP Error keys must be configured.
- Confirm the **paging style** (limit-offset vs marker vs Link header) before build.
- Confirm whether the API supports **change tracking**; delta aggregation is
  otherwise unavailable.
- Group/entitlement aggregation needs manual schema work through the API, so
  budget for it.
- If the target needs a non-form-urlencoded content type for token requests,
  plan for Custom Authentication rather than the OAuth 2.0 type.
