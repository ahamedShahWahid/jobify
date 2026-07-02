import 'package:json_annotation/json_annotation.dart';

part 'job_status.g.dart';

/// Mirrors backend `JobStatus` (`core/src/jobify/db/models.py:404`, a `StrEnum`
/// with members `OPEN="open"`/`CLOSED="closed"`). `unknown` is a client-only
/// sentinel for a value the backend hasn't been mapped to yet — DTO fields
/// using this enum must declare `@JsonKey(unknownEnumValue: JobStatus.unknown)`
/// (done today in `JobSummaryDto.status`). Round-trip pinned by
/// `test/unit/data/jobs/job_status_test.dart`.
@JsonEnum(alwaysCreate: true)
enum JobStatus {
  @JsonValue('open')
  open,
  @JsonValue('closed')
  closed,
  @JsonValue('unknown')
  unknown,
}
