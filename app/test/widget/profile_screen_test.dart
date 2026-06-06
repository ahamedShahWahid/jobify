import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/auth_state.dart';
import 'package:kpa_app/data/auth/user_role.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';
import 'package:kpa_app/presentation/auth/auth_providers.dart';
import 'package:kpa_app/presentation/profile/package_info_provider.dart';
import 'package:kpa_app/presentation/profile/profile_screen.dart';
import 'package:package_info_plus/package_info_plus.dart';

class _FakeRepo implements MeRepository {
  _FakeRepo(this.me);
  final MeDto me;
  @override
  Future<MeDto> fetch() async => me;
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async => me;
}

const _me = MeDto(
  id: 'u1',
  email: 'eng@example.com',
  displayName: 'Eng U',
  role: 'applicant',
  applicant: ApplicantSummaryDto(
    id: 'a1',
    fullName: 'Eng U',
    locations: ['Pune'],
    expectedCtc: '1800000.00',
  ),
);

ProviderScope _buildScope({
  required Widget home,
  AuthState? authState,
}) {
  return ProviderScope(
    overrides: [
      meRepositoryProvider.overrideWithValue(_FakeRepo(_me)),
      packageInfoProvider.overrideWith(
        (_) async => PackageInfo(
          appName: 'KPA',
          packageName: 'com.kpa.app',
          version: '1.0.0',
          buildNumber: '1',
        ),
      ),
      if (authState != null)
        authStateProvider.overrideWithValue(authState),
    ],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: home,
    ),
  );
}

void main() {
  testWidgets(
    'renders user name + email + résumé/notifications/privacy rows + Sign out',
    (tester) async {
      await tester.pumpWidget(_buildScope(home: const ProfileScreen()));
      await tester.pumpAndSettle();
      expect(find.text('Eng U'), findsOneWidget);
      expect(find.text('eng@example.com'), findsOneWidget);
      expect(find.text('Résumé'), findsOneWidget);
      expect(find.text('Notifications'), findsOneWidget);
      expect(find.text('Privacy & data'), findsOneWidget);
      expect(find.text('Locations'), findsOneWidget);
      expect(find.text('Pune'), findsOneWidget);
      expect(find.text('Edit'), findsOneWidget);
      // Sign out button may require scrolling in the test viewport.
      await tester.scrollUntilVisible(
        find.text('Sign out'),
        100,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Sign out'), findsOneWidget);
    },
  );

  testWidgets(
    "shows 'I'm hiring' CTA when signed in as applicant",
    (tester) async {
      await tester.pumpWidget(
        _buildScope(
          home: const ProfileScreen(),
          authState: const SignedIn(
            userId: 'u1',
            email: 'eng@example.com',
            role: UserRole.applicant,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text("I'm hiring — post a job"), findsOneWidget);
    },
  );

  testWidgets(
    "hides 'I'm hiring' CTA when signed in as recruiter",
    (tester) async {
      await tester.pumpWidget(
        _buildScope(
          home: const ProfileScreen(),
          authState: const SignedIn(
            userId: 'u1',
            email: 'eng@example.com',
            role: UserRole.recruiter,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text("I'm hiring — post a job"), findsNothing);
    },
  );
}
