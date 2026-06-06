import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/auth/auth_repository.dart';
import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository.dart';
import 'package:kpa_app/data/employers/employer_repository_impl.dart';
import 'package:kpa_app/presentation/onboarding/employer_onboarding_screen.dart';

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

class _FakeEmployerRepo implements EmployerRepository {
  _FakeEmployerRepo(this._result);

  final EmployerDto _result;

  @override
  Future<EmployerDto> createEmployer({
    required String name,
    String? gst,
  }) async =>
      _result;

  @override
  Future<List<EmployerDto>> listMyEmployers() async => [];
}

class _ThrowingEmployerRepo implements EmployerRepository {
  _ThrowingEmployerRepo(this._error);

  final Exception _error;

  @override
  Future<EmployerDto> createEmployer({
    required String name,
    String? gst,
  }) async =>
      throw _error;

  @override
  Future<List<EmployerDto>> listMyEmployers() async => [];
}

class _FakeAuthRepo implements AuthRepository {
  _FakeAuthRepo(this._state);

  final SignedIn _state;

  @override
  AuthState get current => _state;

  @override
  Future<SignedIn> signInWithGoogle() async => _state;

  @override
  Future<SignedIn> completeWebSignIn(String idToken) async => _state;

  @override
  Future<SignedIn> refreshSession() async => _state;

  @override
  Future<String> refreshAccessTokenForInterceptor() async => 'token';

  @override
  Future<void> signOut() async {}
}

// ---------------------------------------------------------------------------
// Helpers
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

Widget _buildTestWidget({
  required EmployerRepository employerRepo,
  AuthRepository? authRepo,
}) {
  final container = ProviderContainer(
    overrides: [
      employerRepositoryProvider.overrideWithValue(employerRepo),
      authRepositoryProvider
          .overrideWithValue(authRepo ?? _FakeAuthRepo(_recruiterSignedIn)),
    ],
  );

  return UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(
      home: EmployerOnboardingScreen(),
    ),
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  testWidgets(
    'tapping Create company with empty name shows min-2-characters error',
    (tester) async {
      await tester.pumpWidget(
        _buildTestWidget(employerRepo: _FakeEmployerRepo(_acmeEmployer)),
      );
      await tester.pumpAndSettle();

      // Tap the button with no text entered
      await tester.tap(find.widgetWithText(FilledButton, 'Create company'));
      await tester.pumpAndSettle();

      expect(
        find.text('Enter your company name (min 2 characters)'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'entering a valid name clears validation error',
    (tester) async {
      await tester.pumpWidget(
        _buildTestWidget(employerRepo: _FakeEmployerRepo(_acmeEmployer)),
      );
      await tester.pumpAndSettle();

      // First tap to trigger validation
      await tester.tap(find.widgetWithText(FilledButton, 'Create company'));
      await tester.pumpAndSettle();

      expect(
        find.text('Enter your company name (min 2 characters)'),
        findsOneWidget,
      );

      // Now enter a valid name
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Company name'),
        'Acme',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Create company'));
      await tester.pumpAndSettle();

      expect(
        find.text('Enter your company name (min 2 characters)'),
        findsNothing,
      );
    },
  );

  testWidgets(
    'shows employer_name_taken snackbar message on 409 conflict',
    (tester) async {
      await tester.pumpWidget(
        _buildTestWidget(
          employerRepo: _ThrowingEmployerRepo(
            const ApiException(
              statusCode: 409,
              slug: 'employer_name_taken',
              detail: 'An employer with that name already exists.',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Company name'),
        'Acme Corp',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Create company'));
      await tester.pumpAndSettle();

      expect(
        find.text('That company name is already registered.'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'shows generic error snackbar for non-409 errors',
    (tester) async {
      await tester.pumpWidget(
        _buildTestWidget(
          employerRepo: _ThrowingEmployerRepo(
            const ApiException(
              statusCode: 500,
              slug: 'internal_server_error',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Company name'),
        'Acme Corp',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Create company'));
      await tester.pumpAndSettle();

      expect(
        find.text('Could not create employer. Please try again.'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'GST validator: non-empty value with wrong length shows error',
    (tester) async {
      await tester.pumpWidget(
        _buildTestWidget(employerRepo: _FakeEmployerRepo(_acmeEmployer)),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Company name'),
        'Acme Corp',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'GSTIN (optional)'),
        '12345', // not 15 chars
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Create company'));
      await tester.pumpAndSettle();

      expect(
        find.text('GSTIN must be exactly 15 characters'),
        findsOneWidget,
      );
    },
  );
}
