import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/auth/auth_repository.dart';
import 'package:jobify_app/data/auth/auth_repository_provider.dart';
import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/data/employers/employer_dto.dart';
import 'package:jobify_app/data/employers/employer_repository.dart';
import 'package:jobify_app/data/employers/employer_repository_impl.dart';
import 'package:jobify_app/presentation/onboarding/employer_onboarding_controller.dart';

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

class _FakeEmployerRepo implements EmployerRepository {
  _FakeEmployerRepo(this._result);

  final EmployerDto _result;
  int createCalls = 0;

  @override
  Future<EmployerDto> createEmployer({
    required String name,
    String? gst,
  }) async {
    createCalls++;
    return _result;
  }

  @override
  Future<List<EmployerDto>> listMyEmployers() async => [];
}

class _ThrowingEmployerRepo implements EmployerRepository {
  _ThrowingEmployerRepo(this._error);

  final Exception _error;
  int createCalls = 0;

  @override
  Future<EmployerDto> createEmployer({
    required String name,
    String? gst,
  }) async {
    createCalls++;
    throw _error;
  }

  @override
  Future<List<EmployerDto>> listMyEmployers() async => [];
}

class _FakeAuthRepo implements AuthRepository {
  _FakeAuthRepo(this._refreshResult);

  final SignedIn _refreshResult;
  int refreshCalls = 0;

  @override
  AuthState get current => _refreshResult;

  @override
  Future<SignedIn> signInWithGoogle() async => _refreshResult;

  @override
  Future<SignedIn> completeWebSignIn(String idToken) async => _refreshResult;

  @override
  Future<SignedIn> refreshSession() async {
    refreshCalls++;
    return _refreshResult;
  }

  @override
  Future<String> refreshAccessTokenForInterceptor() async => 'token';

  @override
  Future<void> signOut() async {}
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const _recruiterSignedIn = SignedIn(
  userId: 'u1',
  email: 'test@example.com',
  role: UserRole.recruiter,
);

final _acmeEmployer = EmployerDto(
  id: 'e1',
  name: 'Acme',
  createdAt: DateTime(2024),
);

void main() {
  test(
    'happy path: creates employer, refreshes session, state has employer',
    () async {
      final fakeEmployerRepo = _FakeEmployerRepo(_acmeEmployer);
      final fakeAuthRepo = _FakeAuthRepo(_recruiterSignedIn);

      final container = ProviderContainer(
        overrides: [
          employerRepositoryProvider.overrideWithValue(fakeEmployerRepo),
          authRepositoryProvider.overrideWithValue(fakeAuthRepo),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(employerOnboardingControllerProvider.notifier)
          .submit(name: 'Acme');

      expect(fakeEmployerRepo.createCalls, 1);
      expect(fakeAuthRepo.refreshCalls, 1);

      final state = container.read(employerOnboardingControllerProvider);
      expect(state.hasValue, isTrue);
      expect(state.value!.name, 'Acme');
    },
  );

  test(
    'error path: create throws 409, state hasError, refresh never called',
    () async {
      final fakeEmployerRepo = _ThrowingEmployerRepo(
        const ApiException(
          statusCode: 409,
          slug: 'employer_name_taken',
          detail: 'An employer with that name already exists.',
        ),
      );
      final fakeAuthRepo = _FakeAuthRepo(_recruiterSignedIn);

      final container = ProviderContainer(
        overrides: [
          employerRepositoryProvider.overrideWithValue(fakeEmployerRepo),
          authRepositoryProvider.overrideWithValue(fakeAuthRepo),
        ],
      );
      addTearDown(container.dispose);

      await container
          .read(employerOnboardingControllerProvider.notifier)
          .submit(name: 'Acme');

      expect(
        container.read(employerOnboardingControllerProvider).hasError,
        isTrue,
      );
      expect(fakeAuthRepo.refreshCalls, 0);
    },
  );
}
