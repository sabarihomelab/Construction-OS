# Globalization and Preferences

Construction OS must not hardcode one language, one time zone, one currency, one date format, one unit system, or one regional address model into business logic.

## Design goals

- support multiple companies in different countries and regions
- allow organization defaults with per-user overrides where safe
- store canonical values and format only at presentation boundaries
- preserve historical meaning when locale, time zone, currency, or units change
- keep financial/accounting semantics explicit rather than inferred from display formatting
- make all user-facing text translation-ready
- keep locale behavior separate from authorization and tenant isolation

## Configuration hierarchy

Effective presentation preferences are resolved in this order where applicable:

1. system-safe defaults
2. organization defaults
3. project/location defaults where business meaning requires it
4. user preferences

Security, compliance, financial posting, and historical record semantics must not be overridden merely by changing a user display preference.

## Language and localization

All user-facing strings must be referenced through translation keys rather than embedded throughout components.

Examples:

- navigation labels
- button labels
- validation messages
- status names shown to users
- help text
- notifications
- emails
- report labels
- accessibility labels

Initial development may ship with English only, but the codebase must be translation-ready from the start.

Company and user settings should support a locale such as `en-US`, `en-GB`, `en-IN`, `fr-FR`, etc. The locale controls presentation, not stored business meaning.

## Time zones

Use IANA time zone identifiers such as:

- `Asia/Kolkata`
- `America/New_York`
- `Europe/London`

Do not persist ambiguous abbreviations such as IST, CST, or EST as authoritative time-zone identifiers.

### Storage rule

- event timestamps are stored as timezone-aware instants, normalized to UTC
- the relevant business/local time zone is stored separately where required
- date-only business values remain dates and are not converted through UTC

Examples of date-only values:

- invoice date
- work date
- accounting period date
- contract effective date

Examples of instant values:

- login timestamp
- file upload timestamp
- audit event timestamp
- API request timestamp

### Project/site time zones

Projects may operate in a different time zone from the company's headquarters. Field records such as daily logs, shifts, weather observations, and attendance may therefore require a project/site time zone.

Historical records must retain sufficient context to explain which local day/time applied when the record was created.

## Date and time presentation

Do not hardcode date display formats such as `MM/DD/YYYY`.

Presentation may follow locale/user preference, for example:

- `09/10/2026`
- `10/09/2026`
- `10 Sep 2026`

Machine-facing APIs use unambiguous ISO-8601 representations.

Users may choose 12-hour or 24-hour display where appropriate.

## Currency

Store currency using ISO 4217 currency codes, for example:

- `USD`
- `INR`
- `GBP`
- `EUR`

Money values are never represented internally using floating-point arithmetic.

Each monetary value that can vary by currency must preserve its currency code or inherit it from an immutable transaction/accounting context.

Organization defaults may define a base currency, while future multi-currency modules may support transaction currency, exchange-rate source, rate date, and reporting currency explicitly.

Changing a company's display/default currency must never silently reinterpret historical financial records.

## Numbers and decimal formatting

Formatting follows locale at the UI/report boundary.

Examples:

- `1,234.56`
- `1.234,56`

Stored numeric values remain locale-independent.

## Measurement units

Construction OS must support configurable measurement systems and explicit units.

Examples:

- length: mm, cm, m, in, ft
- area: m², ft²
- volume: m³, yd³
- mass: kg, t, lb
- temperature: °C, °F
- pressure and other trade-specific units where required

Business records that depend on units must store the unit identity with the value or reference a defined unit context. Display conversion must not alter the source measurement.

## Addresses and regional fields

Do not assume one address format.

Address support must allow regional variation in:

- street/locality
- city/town
- district/county
- state/province/region
- postal/ZIP code
- country

Country codes should use ISO standards where practical.

## Phone numbers

Store normalized phone numbers using an international representation where possible. Presentation formatting may vary by locale.

## Week, calendar, and working-time preferences

Organization/project preferences may include:

- first day of week
- working days
- default workday start/end
- holidays/calendar sets
- payroll week boundaries
- fiscal year configuration

These settings must be version-aware when they affect historical calculations or reporting.

## Regional terminology

Labels may vary by market or company preference without changing canonical internal object names.

Examples might include differences in terminology for:

- labor / labour
- ZIP / postal code
- subcontractor / trade partner
- superintendent / site manager

Configured display terminology must not change API keys, permission keys, or database identifiers.

## Accessibility

Localization must work together with accessibility requirements:

- keyboard navigation
- screen-reader labels
- text scaling
- contrast
- touch targets
- non-color-only status indicators
- translated accessibility text

## Notifications

Notifications must respect:

- user language
- user time zone
- quiet hours
- organization policy
- delivery channel preferences

Scheduled notifications must preserve the intended local time across daylight-saving changes.

## Reports and exports

Reports should explicitly state relevant context where ambiguity could matter, including:

- time zone
- currency
- units
- locale/date format when needed
- generated timestamp

Machine-readable exports should prefer stable canonical values and explicit codes rather than localized display text.

## Search and help

Search should tolerate localized labels while retaining canonical object/field keys.

The Help/Knowledge system should use the current page, language, organization terminology, and user permissions to present relevant help content without changing authorization behavior.

## Data migration and compatibility

Changing any of the following requires impact assessment when historical meaning may be affected:

- company time zone
- project/site time zone
- base currency
- fiscal year
- unit defaults
- working calendar
- locale-dependent business rules

Display-only preference changes generally do not rewrite historical records.

## No-hardcode rule

Business code must not embed assumptions such as:

- English is the only language
- USD is the only currency
- the server time zone is the business time zone
- dates are always MM/DD/YYYY
- every project uses the company headquarters time zone
- all measurements use imperial or metric units
- every country has the same address format

These assumptions must be represented through configuration, canonical data types, or explicit domain rules.
