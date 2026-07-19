import 'package:jobify_app/data/feed/match_feedback_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';

abstract interface class JobsRepository {
  Future<JobDetailDto> fetchById(String jobId);
  Future<ApplicationDto> applyTo(
    String jobId, {
    ApplicationSource source = ApplicationSource.feed,
  });
  Future<SavedJobDto> save(String jobId);
  Future<void> unsave(String jobId);
  Future<MatchFeedbackDto> rateMatch(String jobId, MatchFeedbackRating rating);
  Future<void> clearMatchFeedback(String jobId);
}
