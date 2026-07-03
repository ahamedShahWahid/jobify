import 'package:json_annotation/json_annotation.dart';

part 'application_status.g.dart';

/// Mirrors backend `ApplicationStatus` (`core/src/jobify/db/models.py:670`, a
/// `StrEnum` with members `APPLIED="applied"`/`WITHDRAWN="withdrawn"`).
/// `unknown` is a client-only sentinel — DTO fields using this enum must
/// declare `@JsonKey(unknownEnumValue: ApplicationStatus.unknown)` (done today
/// in `ApplicationDto.status`). Round-trip pinned by
/// `test/unit/data/jobs/application_status_test.dart`.
@JsonEnum(alwaysCreate: true)
enum ApplicationStatus {
  @JsonValue('applied')
  applied,
  @JsonValue('withdrawn')
  withdrawn,
  @JsonValue('unknown')
  unknown,
}
