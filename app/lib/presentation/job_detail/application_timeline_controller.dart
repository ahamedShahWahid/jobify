import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'application_timeline_controller.g.dart';

/// Stage-change events for one application. Family keyed by applicationId;
/// consumed by `_ApplicationTimeline` in job_detail_screen.dart.
@riverpod
Future<List<StageEventDto>> applicationTimeline(
  Ref ref,
  String applicationId,
) =>
    ref.read(applicationsRepositoryProvider).fetchTimeline(applicationId);
