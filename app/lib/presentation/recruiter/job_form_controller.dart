import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_dashboard_controller.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_controller.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'job_form_controller.g.dart';

class JobFormData {
  const JobFormData({
    required this.title,
    required this.description,
    required this.locations,
    required this.minExpYears,
    required this.maxExpYears,
    this.ctcMin,
    this.ctcMax,
    this.status = 'open',
  });

  final String title;
  final String description;
  final List<String> locations;
  final int minExpYears;
  final int maxExpYears;
  final double? ctcMin;
  final double? ctcMax;
  final String status;

  Map<String, dynamic> toCreateBody(String employerId) {
    final body = <String, dynamic>{
      'employer_id': employerId,
      'title': title,
      'description': description,
      'locations': locations,
      'min_exp_years': minExpYears,
      'max_exp_years': maxExpYears,
      'status': status,
    };
    if (ctcMin != null) body['ctc_min'] = ctcMin;
    if (ctcMax != null) body['ctc_max'] = ctcMax;
    return body;
  }

  Map<String, dynamic> toPatchBody() {
    final body = <String, dynamic>{
      'title': title,
      'description': description,
      'locations': locations,
      'min_exp_years': minExpYears,
      'max_exp_years': maxExpYears,
      'status': status,
    };
    if (ctcMin != null) body['ctc_min'] = ctcMin;
    if (ctcMax != null) body['ctc_max'] = ctcMax;
    return body;
  }
}

@riverpod
class JobFormController extends _$JobFormController {
  @override
  FutureOr<RecruiterJobDto?> build() => null;

  Future<void> create({
    required String employerId,
    required JobFormData data,
  }) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(recruiterJobsRepositoryProvider);
      final job = await repo.createJob(data.toCreateBody(employerId));
      ref
        ..invalidate(recruiterDashboardControllerProvider)
        ..invalidate(recruiterJobsControllerProvider);
      return job;
    });
  }

  Future<void> editJob({
    required String jobId,
    required JobFormData data,
  }) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(recruiterJobsRepositoryProvider);
      final job = await repo.patchJob(jobId, data.toPatchBody());
      ref
        ..invalidate(recruiterDashboardControllerProvider)
        ..invalidate(recruiterJobsControllerProvider);
      return job;
    });
  }

  Future<void> close(String jobId) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(recruiterJobsRepositoryProvider);
      final job = await repo.patchJob(jobId, {'status': 'closed'});
      ref
        ..invalidate(recruiterDashboardControllerProvider)
        ..invalidate(recruiterJobsControllerProvider);
      return job;
    });
  }

  Future<void> delete(String jobId) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(recruiterJobsRepositoryProvider).deleteJob(jobId);
      ref
        ..invalidate(recruiterDashboardControllerProvider)
        ..invalidate(recruiterJobsControllerProvider);
      return null;
    });
  }
}
