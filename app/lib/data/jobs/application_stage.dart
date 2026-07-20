import 'package:json_annotation/json_annotation.dart';

/// Recruiter hiring-pipeline stage.
///
/// Mirrors backend `ApplicationStage` in `core/src/jobify/db/models.py`;
/// pinned by test/unit/data/jobs/application_stage_test.dart. `unknown` is
/// the unrecognised-server-value sentinel — it must NEVER serialize.
enum ApplicationStage {
  @JsonValue('applied')
  applied,
  @JsonValue('shortlisted')
  shortlisted,
  @JsonValue('interview')
  interview,
  @JsonValue('offer')
  offer,
  @JsonValue('hired')
  hired,
  @JsonValue('rejected')
  rejected,
  unknown,
}

extension ApplicationStageWire on ApplicationStage {
  String get wireValue => switch (this) {
        ApplicationStage.applied => 'applied',
        ApplicationStage.shortlisted => 'shortlisted',
        ApplicationStage.interview => 'interview',
        ApplicationStage.offer => 'offer',
        ApplicationStage.hired => 'hired',
        ApplicationStage.rejected => 'rejected',
        ApplicationStage.unknown =>
          throw StateError('ApplicationStage.unknown is not a wire value'),
      };
}
