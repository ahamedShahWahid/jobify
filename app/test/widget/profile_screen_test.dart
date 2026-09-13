import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/auth/auth_state.dart';
import 'package:jobify_app/data/auth/user_role.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/l10n/app_localizations.dart';
import 'package:jobify_app/presentation/auth/auth_providers.dart';
import 'package:jobify_app/presentation/profile/package_info_provider.dart';
import 'package:jobify_app/presentation/profile/profile_screen.dart';
import 'package:jobify_app/presentation/routing/locale_controller.dart';
import 'package:package_info_plus/package_info_plus.dart';

class _FakeRepo implements MeRepository {
  _FakeRepo(this.me);
  final MeDto me;
  @override
  Future<MeDto> fetch() async => me;
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async => me;
}

class _FakePrefsRepo implements PreferencesRepository {
  @override
  Future<PreferencesDto> fetch() async => const PreferencesDto(
    desiredRole: null,
    locations: ['Pune'],
    expectedCtc: '1800000.00',
  );
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async => fetch();
}

/// Records every `update()` call so the language-switcher test can assert
/// on the exact DTO the switcher sent.
class _RecordingPrefsRepo implements PreferencesRepository {
  final List<PreferencesUpdateDto> updates = [];

  @override
  Future<PreferencesDto> fetch() async => const PreferencesDto(
    desiredRole: null,
    locations: ['Pune'],
    expectedCtc: '1800000.00',
  );

  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    updates.add(update);
    return PreferencesDto(
      desiredRole: update.desiredRole,
      locations: update.locations,
      expectedCtc: update.expectedCtc?.toString(),
      language: update.language,
    );
  }
}

const _me = MeDto(
  id: 'u1',
  email: 'eng@example.com',
  displayName: 'Eng U',
  role: 'applicant',
  applicant: ApplicantSummaryDto(id: 'a1', fullName: 'Eng U'),
);

ProviderScope _buildScope({required Widget home, AuthState? authState}) {
  return ProviderScope(
    overrides: [
      meRepositoryProvider.overrideWithValue(_FakeRepo(_me)),
      preferencesRepositoryProvider.overrideWithValue(_FakePrefsRepo()),
      packageInfoProvider.overrideWith(
        (_) async => PackageInfo(
          appName: 'Jobify',
          packageName: 'com.jobify.app',
          version: '1.0.0',
          buildNumber: '1',
        ),
      ),
      if (authState != null) authStateProvider.overrideWithValue(authState),
    ],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: home,
    ),
  );
}

void main() {
  testWidgets('spec-sheet values and Add prompts sit flush at the row end, '
      'even on a wide viewport', (tester) async {
    // Regression: `Spacer()` + loose `Flexible` split the free width 50/50,
    // parking every value at mid-row instead of the right edge.
    await tester.binding.setSurfaceSize(const Size(1000, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(_buildScope(home: const ProfileScreen()));
    await tester.pumpAndSettle();

    double rowEnd(Finder child) =>
        tester
            .getTopRight(
              find.ancestor(of: child, matching: find.byType(Row)).first,
            )
            .dx;

    final value = find.text('Pune');
    expect(tester.getTopRight(value).dx, closeTo(rowEnd(value), 1));

    // `_FakePrefsRepo` has no desired role, so that row shows the Add prompt.
    final add =
        find
            .ancestor(
              of: find.text(
                lookupAppLocalizations(
                  const Locale('en'),
                ).profileAddFieldAction,
              ),
              matching: find.byType(InkWell),
            )
            .first;
    expect(tester.getTopRight(add).dx, closeTo(rowEnd(add), 1));
  });

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
      // Flush the Arrive entrance-animation timers for the rows below the
      // fold (the language switcher added one more staggered index) so none
      // are still pending when the widget tree is disposed at teardown.
      await tester.pumpAndSettle();
      expect(find.text('Sign out'), findsOneWidget);
    },
  );

  testWidgets("shows 'I'm hiring' CTA when signed in as applicant", (
    tester,
  ) async {
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
  });

  testWidgets("hides 'I'm hiring' CTA when signed in as recruiter", (
    tester,
  ) async {
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
  });

  testWidgets('tapping हिन्दी on the language switcher saves language "hi" and '
      'flips the app locale', (tester) async {
    final repo = _RecordingPrefsRepo();
    final container = ProviderContainer(
      overrides: [
        meRepositoryProvider.overrideWithValue(_FakeRepo(_me)),
        preferencesRepositoryProvider.overrideWithValue(repo),
        packageInfoProvider.overrideWith(
          (_) async => PackageInfo(
            appName: 'Jobify',
            packageName: 'com.jobify.app',
            version: '1.0.0',
            buildNumber: '1',
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: ThemeData.light(useMaterial3: true),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const ProfileScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.text('हिन्दी'),
      100,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('हिन्दी'));
    await tester.pumpAndSettle();

    expect(repo.updates, isNotEmpty);
    expect(repo.updates.last.language, 'hi');
    expect(container.read(localeControllerProvider), const Locale('hi'));
  });
}
