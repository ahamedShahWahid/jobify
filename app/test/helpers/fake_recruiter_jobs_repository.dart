import 'dart:typed_data';

import 'package:kpa_app/data/jobs/applicant_of_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_api.dart';
import 'package:kpa_app/data/jobs/recruiter_jobs_repository.dart';

/// Configurable in-memory [RecruiterJobsRepository] for widget tests.
///
/// Records the last create/patch/delete/download call so assertions can verify
/// the screen forwarded the right payload.
class FakeRecruiterJobsRepository implements RecruiterJobsRepository {
  FakeRecruiterJobsRepository({
    this.jobsPage = const RecruiterJobsPageDto(items: []),
    this.applicantsPage = const ApplicantsOfJobPageDto(items: []),
    this.resume,
  });

  RecruiterJobsPageDto jobsPage;
  ApplicantsOfJobPageDto applicantsPage;
  ResumeDownload? resume;

  Map<String, dynamic>? createdBody;
  String? patchedId;
  Map<String, dynamic>? patchedBody;
  String? deletedId;
  String? downloadedApplicationId;

  @override
  Future<RecruiterJobsPageDto> listMyJobs({
    String? status,
    String? cursor,
    int limit = 20,
  }) async =>
      jobsPage;

  @override
  Future<RecruiterJobDto> createJob(Map<String, dynamic> body) async {
    createdBody = body;
    return fakeRecruiterJob(id: 'created');
  }

  @override
  Future<RecruiterJobDto> patchJob(String id, Map<String, dynamic> body) async {
    patchedId = id;
    patchedBody = body;
    return fakeRecruiterJob(id: id);
  }

  @override
  Future<void> deleteJob(String id) async {
    deletedId = id;
  }

  @override
  Future<ApplicantsOfJobPageDto> listApplicants(
    String jobId, {
    String? cursor,
    int limit = 20,
  }) async =>
      applicantsPage;

  @override
  Future<ResumeDownload> downloadResume(String applicationId) async {
    downloadedApplicationId = applicationId;
    return resume ??
        ResumeDownload(
          bytes: Uint8List.fromList(const [1, 2, 3]),
          filename: 'resume.pdf',
          contentType: 'application/pdf',
        );
  }
}

/// Test factory for a [RecruiterJobDto] with sensible defaults.
RecruiterJobDto fakeRecruiterJob({
  required String id,
  String title = 'Senior Engineer',
  String status = 'open',
  List<String> locations = const ['Bengaluru'],
  int minExpYears = 2,
  int maxExpYears = 6,
  double? ctcMin,
  double? ctcMax,
  int applicantCount = 0,
  int surfacedMatchCount = 0,
}) =>
    RecruiterJobDto(
      id: id,
      title: title,
      description: 'A great role doing great things.',
      locations: locations,
      minExpYears: minExpYears,
      maxExpYears: maxExpYears,
      ctcMin: ctcMin,
      ctcMax: ctcMax,
      status: status,
      postedAt: DateTime.utc(2026),
      employerVerified: true,
      applicantCount: applicantCount,
      surfacedMatchCount: surfacedMatchCount,
    );

/// Test factory for an [ApplicantOfJobDto].
ApplicantOfJobDto fakeApplicantOfJob({
  String applicationId = 'app1',
  String applicantId = 'a1',
  String? displayName = 'Alice Candidate',
  String? email = 'alice@example.com',
  String status = 'applied',
  double? matchScore = 0.82,
  Map<String, String>? matchExplanation = const {'fit': 'Strong skills match.'},
}) =>
    ApplicantOfJobDto(
      applicationId: applicationId,
      applicantId: applicantId,
      displayName: displayName,
      email: email,
      status: status,
      appliedAt: DateTime.utc(2026),
      matchScore: matchScore,
      matchExplanation: matchExplanation,
    );
