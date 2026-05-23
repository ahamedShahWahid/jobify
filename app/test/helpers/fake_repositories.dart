import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/jobs/jobs_dto.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/domain/auth/auth_repository.dart';
import 'package:kpa_app/domain/auth/auth_state.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';
import 'package:kpa_app/domain/jobs/applications_repository.dart';
import 'package:kpa_app/domain/jobs/jobs_repository.dart';
import 'package:kpa_app/domain/jobs/saved_jobs_repository.dart';
import 'package:kpa_app/domain/me/me_repository.dart';

class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository({AuthState initial = const SignedOut()})
      : _state = initial;
  AuthState _state;

  @override
  AuthState get current => _state;
  @override
  Future<SignedIn> signInWithGoogle() async {
    const si = SignedIn(userId: 'u1', email: 'u@e.com', displayName: 'U');
    _state = si;
    return si;
  }

  @override
  Future<SignedIn> refreshSession() async {
    const si = SignedIn(userId: 'u1', email: 'u@e.com', displayName: 'U');
    _state = si;
    return si;
  }

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

  @override
  Future<JobDetailDto> fetchById(String id) async => _detail;

  @override
  Future<ApplicationDto> applyTo(
    String jobId, {
    String source = 'feed',
  }) async {
    final app = ApplicationDto(
      id: 'a1',
      applicantId: 'p',
      jobId: jobId,
      status: 'applied',
      source: source,
      createdAt: DateTime.now(),
    );
    _detail = _detail.copyWith(application: app);
    return app;
  }

  @override
  Future<SavedJobDto> save(String jobId) async {
    final s = SavedJobDto(
      id: 's1',
      applicantId: 'p',
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
}

class FakeApplicationsRepository implements ApplicationsRepository {
  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      const ApplicationsPageDto(items: []);

  @override
  Future<ApplicationDto> withdraw(String id) async => ApplicationDto(
        id: id,
        applicantId: 'p',
        jobId: 'j1',
        status: 'withdrawn',
        source: 'feed',
        createdAt: DateTime.now(),
        withdrawnAt: DateTime.now(),
      );
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
  Future<MeDto> fetch() async => MeDto(
        user: MeUserDto(
          id: 'u1',
          email: 'u@e.com',
          displayName: 'U',
          role: 'applicant',
          createdAt: DateTime(2026),
        ),
        applicant: const ApplicantSummaryDto(id: 'a1', userId: 'u1'),
      );
}
