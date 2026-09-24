# ISC JDBC Connector — configuration reference

Condensed from SailPoint Identity Security Cloud connector documentation
(documentation.sailpoint.com/connectors/jdbc/, revised 09 September 2026).
Source links are given per section.

## What it is

A direct-connect source that reads user data from any database with a JDBC
driver. You supply SQL queries; the connector runs them against the database.
To govern the loaded data you either build an identity profile on the source or
correlate the accounts to existing identities.
Source: /integrating_jdbc/introduction.html

CAUTION — default correlation. JDBC sources ship with a default correlation
configuration that matches the identity **Display Name** against the source
**displayName** attribute. Display names are neither unique nor immutable, so
this default must be replaced during onboarding.
Source: /integrating_jdbc/introduction.html

## Prerequisites

- At least one virtual appliance (VA) cluster configured and connection-tested.
  JDBC is never cloud-direct; it always runs through a VA.
- A service account on the target database.
- The correct JDBC driver JAR for that database.
- To load entitlements you must add the entitlement schema to the source
  configuration; see "Configuring Multiple Group Objects".
- Snowflake key-pair auth requires a generated encrypted public/private key pair.
- Snowflake OAuth 2.0 requires an external IdP and a Snowflake security integration.
- Provisioning is a separately purchased feature and requires SailPoint Services
  to implement it for the environment.
- Password Management is likewise separately purchased and Services-implemented.

Source: /integrating_jdbc/prerequisites.html

## Supported databases

IBM DB2 (Windows), Oracle DB, Sybase (SAP ASE), Microsoft SQL Server, MySQL,
PostgreSQL, and AWS RDS. Any database with a JDBC driver is supported in
principle; version requirements follow the direct database connection
requirements.
Source: /integrating_jdbc/system_requirements.html

## Base configuration

Fields on the Base Configuration page:

| Field | Notes |
| --- | --- |
| Source Name | Must be unique across sources |
| Source Description | Must distinguish it from similar sources |
| Source Owner | Type 2+ letters to match |
| Virtual Appliance Cluster | The cluster acting as application connector |
| Governance Group for Source Management | Optional |
| Enable Provisioning | **Permanent — once enabled it cannot be disabled** |
| Upload Files (JDBC driver) | Driver JAR for the database; upload history is retained |
| SQLJDBCDriver.config + krb5.config | Only for MS SQL Server via Windows/Kerberos authentication |

After uploading the Kerberos config files you may need to restart the Cloud
Connection Gateway (CCG) service on the VA so a stale cached config is dropped.

Driver JARs must be downloaded from a trusted source with valid TLS certificates
and verified by digital signature or checksum.

Source: /integrating_jdbc/base_configuration.html

## Account query settings

Three queries, each with an optional "use stored procedure" toggle:

1. **Test Connection SQL Query** — a simple query proving connectivity.
2. **Account SQL Query** — loads all accounts.
   Example: `SELECT userid, fname, lname FROM users`
3. **Single Account SQL Query** — loads one account. Usually the account query
   plus a `WHERE` clause using the `$(identity)` placeholder, which the connector
   replaces at runtime with the account's NativeIdentity.
   Example: `SELECT userid, fname, lname FROM users WHERE userid = '$(identity)'`

IMPORTANT: SQL entries must **not** end with a semicolon. A trailing `;` produces
a generic error message.

Source: /integrating_jdbc/account_query_settings.html

## Group (entitlement) query settings

- **Group SQL Query** — loads groups. Groups are used as entitlements.
- **Single Group SQL Query** — loads one group.
- Both have "use stored procedure" toggles.
- The same no-trailing-semicolon rule applies.
- Multiple group objects are supported via "Configuring Multiple Group Objects".

Source: /integrating_jdbc/group_query_settings.html

## Schema discovery and aggregation

Discover Schema detects attributes from the query result set. Accounts and
entitlements are then loaded by their respective aggregation tasks.
Sources: /integrating_jdbc/discover_schema.html, /loading_accounts.html,
/loading_entitlements.html

## Provisioning query settings

Requires "Configure Provisioning Operations in the Connector" to be enabled in
the source configuration.

Provisioning can be done either by provisioning rules or by SQL queries and
stored procedures configured in the connector.

Supported functionality:

- Single SQL query execution
- Multiple SQL query execution
- Stored procedures, e.g. `Call procedure_name($plan.attribute1$, $plan.attribute2$)`
- Inline variables from the provisioning plan: `$plan.fieldname.fieldtype$`
- Chaining: response items from previously executed queries in the same query
  set, via `$response.fieldname.fieldtype$`
- Type safety: if no data type is declared the field is treated as a string.

Supported data types (case-insensitive):

| Type | Token |
| --- | --- |
| String | `Str`, `Varchar` |
| Integer | `Int` |
| Boolean | `Bool` |
| Date | `Date` |
| Double | `Dbl` |
| Float | `Flt` |

Examples: `$plan.firstName.string$`, `$response.id.int$`

Per-operation configuration pages exist for Create Account, Update Account,
Enable/Disable/Unlock Account, Delete Account, and Multiple Query Execution.

Source: /integrating_jdbc/provisioning_query_settings.html

## Onboarding implications

- No VA cluster means no JDBC source. Confirm cluster and firewall path early.
- Enabling provisioning is irreversible, so decide read-only vs provisioning
  before creating the source.
- Provisioning and password management carry commercial and Services
  dependencies that add lead time.
- The default display-name correlation must be replaced with a unique,
  immutable identifier before go-live.
- A database view purpose-built for ISC is usually safer than querying base
  tables, and insulates the integration from schema churn.
