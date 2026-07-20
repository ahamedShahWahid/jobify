import 'package:jobify_app/data/auth/auth_repository.dart';
import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/data/consents/consent_dto.dart';
import 'package:jobify_app/data/consents/consents_repository.dart';
import 'package:jobify_app/data/dsr/dsr_dto.dart';
import 'package:jobify_app/data/dsr/dsr_repository.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_repository.dart';
import 'package:jobify_app/data/feed/match_feedback_dto.dart';
import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/jobs_repository.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';

class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository({AuthState initial = const SignedOut()})
      : _state = initial;
  AuthState _state;

  @override
  AuthState get current => _state;
  @override
  Future<SignedIn> signInWithGoogle() async {
    const si = SignedIn(
      userId: 'u1',
      email: 'u@e.com',
      role: UserRole.applicant,
      displayName: 'U',
    );
    _state = si;
    return si;
  }

  @override
  Future<SignedIn> completeWebSignIn(String idToken) async {
    const si = SignedIn(
      userId: 'u1',
      email: 'u@e.com',
      role: UserRole.applicant,
      displayName: 'U',
    );
    _state = si;
    return si;
  }

  @override
  Future<SignedIn> refreshSession() async {
    const si = SignedIn(
      userId: 'u1',
      email: 'u@e.com',
      role: UserRole.applicant,
      displayName: 'U',
    );
    _state = si;
    return si;
  }

  @override
  Future<String> refreshAccessTokenForInterceptor() async => 'ACCESS';

  @override
  Future<void> signOut() async {
    _state = const SignedOut();
  }
}

class FakeFeedRepository implements FeedRepository {
  FakeFeedRepository({required this.items});
  final List<FeedItemDto> items;
  @override
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async {
    return FeedPageDto(items: items);
  }
}

class FakeJobsRepository implements JobsRepository {
  FakeJobsRepository({required JobDetailDto detail}) : _detail = detail;
  JobDetailDto _detail;

  /// Job ids passed to `rateMatch(id, up)`/`rateMatch(id, down)` — recorded
  /// even when [rateMatchError] makes the call throw.
  final List<String> ratedUp = [];
  final List<String> ratedDown = [];
  final List<String> clearedFeedback = [];

  /// When set, `rateMatch` throws this (wrapped in an Exception) instead of
  /// succeeding — lets tests exercise the optimistic-rollback path.
  Object? rateMatchError;

  @override
  Future<JobDetailDto> fetchById(String id) async => _detail;

  @override
  Future<ApplicationDto> applyTo(
    String jobId, {
    ApplicationSource source = ApplicationSource.feed,
  }) async {
    final app = ApplicationDto(
      id: 'a1',
      jobId: jobId,
      status: ApplicationStatus.applied,
      source: source,
      stage: ApplicationStage.applied,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
    _detail = _detail.copyWith(application: app);
    return app;
  }

  @override
  Future<SavedJobDto> save(String jobId) async {
    final s = SavedJobDto(
      id: 's1',
      jobId: jobId,
      createdAt: DateTime.now(),
    );
    _detail = _detail.copyWith(savedJob: s);
    return s;
  }

  @override
  Future<void> unsave(String jobId) async {
    _detail = _detail.copyWith(savedJob: null);
  }

  @override
  Future<MatchFeedbackDto> rateMatch(
    String jobId,
    MatchFeedbackRating rating,
  ) async {
    if (rating == MatchFeedbackRating.up) {
      ratedUp.add(jobId);
    } else if (rating == MatchFeedbackRating.down) {
      ratedDown.add(jobId);
    }
    final err = rateMatchError;
    if (err != null) throw Exception(err.toString());
    final now = DateTime.now();
    _applyMyFeedback(rating);
    return MatchFeedbackDto(
      id: 'f1',
      jobId: jobId,
      rating: rating,
      createdAt: now,
      updatedAt: now,
    );
  }

  @override
  Future<void> clearMatchFeedback(String jobId) async {
    clearedFeedback.add(jobId);
    _applyMyFeedback(null);
  }

  void _applyMyFeedback(MatchFeedbackRating? myFeedback) {
    final m = _detail.match;
    if (m == null) return;
    _detail = _detail.copyWith(
      match: MatchSummaryDto(
        id: m.id,
        totalScore: m.totalScore,
        scoreComponents: m.scoreComponents,
        explanation: m.explanation,
        surfacedAt: m.surfacedAt,
        myFeedback: myFeedback,
      ),
    );
  }
}

class FakeApplicationsRepository implements ApplicationsRepository {
  /// Configured timeline events keyed by application id — set before the
  /// call to control what `fetchTimeline` returns.
  final Map<String, List<StageEventDto>> timelines = {};

  /// Application ids passed to `fetchTimeline`, recorded in call order.
  final List<String> fetchedTimelineIds = [];

  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      const ApplicationsPageDto(items: []);

  @override
  Future<ApplicationDto> withdraw(String id) async => ApplicationDto(
        id: id,
        jobId: 'j1',
        status: ApplicationStatus.withdrawn,
        source: ApplicationSource.feed,
        stage: ApplicationStage.applied,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

  @override
  Future<List<StageEventDto>> fetchTimeline(String applicationId) async {
    fetchedTimelineIds.add(applicationId);
    return timelines[applicationId] ?? [];
  }
}

class FakeSavedJobsRepository implements SavedJobsRepository {
  @override
  Future<SavedJobsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      const SavedJobsPageDto(items: []);
}

class FakeMeRepository implements MeRepository {
  @override
  Future<MeDto> fetch() async => const MeDto(
        id: 'u1',
        email: 'u@e.com',
        displayName: 'U',
        role: 'applicant',
        applicant: ApplicantSummaryDto(id: 'a1', fullName: 'U'),
      );

  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async => const MeDto(
        id: 'u1',
        email: 'u@e.com',
        displayName: 'U',
        role: 'applicant',
        applicant: ApplicantSummaryDto(id: 'a1', fullName: 'U'),
      );
}

class FakeConsentsRepository implements ConsentsRepository {
  FakeConsentsRepository({List<ConsentDto>? initial})
      : items = initial ?? _defaultItems();

  List<ConsentDto> items;
  int patchCallCount = 0;
  Object? patchError;

  @override
  Future<ConsentListResponse> list() async => ConsentListResponse(items: items);

  @override
  Future<ConsentDto> patch(String scope, {required bool granted}) async {
    patchCallCount++;
    if (patchError != null) throw Exception(patchError.toString());
    final next = ConsentDto(
      scope: scope,
      granted: granted,
      updatedAt: DateTime.now().toUtc(),
    );
    items = items.map((c) => c.scope == scope ? next : c).toList();
    return next;
  }

  static List<ConsentDto> _defaultItems() => [
        ConsentDto(
          scope: 'email_transactional',
          granted: true,
          updatedAt: DateTime.utc(2026),
        ),
        ConsentDto(
          scope: 'email_marketing',
          granted: false,
          updatedAt: DateTime.utc(2026),
        ),
        ConsentDto(
          scope: 'in_app_notifications',
          granted: true,
          updatedAt: DateTime.utc(2026),
        ),
      ];
}

class FakeDsrRepository implements DsrRepository {
  String exportPayload = '{"version":"1","exported_at":"..."}';
  Object? exportError;
  DsrDeleteResponse? deleteResponse;
  Object? deleteError;
  int exportCallCount = 0;
  int deleteCallCount = 0;

  @override
  Future<String> exportData() async {
    exportCallCount++;
    if (exportError != null) throw Exception(exportError.toString());
    return exportPayload;
  }

  @override
  Future<DsrDeleteResponse> deleteAccount() async {
    deleteCallCount++;
    if (deleteError != null) throw Exception(deleteError.toString());
    return deleteResponse ??
        DsrDeleteResponse(
          deletedAt: DateTime.utc(2026, 5, 29),
          sectionCounts: const {'notifications': 0, 'user_tombstoned': 1},
          warnings: const [],
        );
  }
}
