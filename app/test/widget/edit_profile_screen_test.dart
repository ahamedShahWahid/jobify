import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/presentation/profile/edit_profile_screen.dart';

class _CapturingMeRepo implements MeRepository {
  ProfileUpdateDto? captured;
  @override
  Future<MeDto> fetch() async => const MeDto(
        id: 'u1',
        email: 'e@e.com',
        role: 'applicant',
        applicant: ApplicantSummaryDto(id: 'a1', fullName: 'Alice'),
      );
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    captured = update;
    return fetch();
  }
}

class _CapturingPrefsRepo implements PreferencesRepository {
  _CapturingPrefsRepo({
    this.dto = const PreferencesDto(
      desiredRole: null,
      locations: ['Pune'],
      expectedCtc: null,
    ),
    this.failUpdate = false,
  });
  final PreferencesDto dto;
  final bool failUpdate;
  PreferencesUpdateDto? captured;
  @override
  Future<PreferencesDto> fetch() async => dto;
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    if (failUpdate) throw Exception('boom');
    captured = update;
    return dto;
  }
}

/// Preferences fetch that never resolves — the form (and Save) must be
/// unreachable, otherwise a half-seeded save wipes server-side values.
class _PendingPrefsRepo implements PreferencesRepository {
  @override
  Future<PreferencesDto> fetch() => Completer<PreferencesDto>().future;
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) =>
      Completer<PreferencesDto>().future;
}

Future<void> _pump(
  WidgetTester tester, {
  required MeRepository meRepo,
  required PreferencesRepository prefsRepo,
  bool settle = true,
}) async {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, __) => const EditProfileScreen()),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        meRepositoryProvider.overrideWithValue(meRepo),
        preferencesRepositoryProvider.overrideWithValue(prefsRepo),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  if (settle) await tester.pumpAndSettle();
}

void main() {
  testWidgets('renders seeded values, adds a chip, saves both endpoints',
      (tester) async {
    final meRepo = _CapturingMeRepo();
    final prefsRepo = _CapturingPrefsRepo();
    await _pump(tester, meRepo: meRepo, prefsRepo: prefsRepo);

    expect(find.text('Pune'), findsOneWidget); // seeded chip

    await tester.enterText(
      find.widgetWithText(TextField, 'Add location'),
      'Mumbai',
    );
    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    expect(find.text('Mumbai'), findsOneWidget);

    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(meRepo.captured, isNotNull);
    expect(meRepo.captured!.fullName, 'Alice');
    expect(prefsRepo.captured, isNotNull);
    expect(prefsRepo.captured!.locations, ['Pune', 'Mumbai']);
  });

  testWidgets('out-of-range experience blocks save', (tester) async {
    final meRepo = _CapturingMeRepo();
    final prefsRepo = _CapturingPrefsRepo();
    await _pump(tester, meRepo: meRepo, prefsRepo: prefsRepo);

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Years of experience'),
      '99', // exceeds max 60
    );
    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(find.text('Must be between 0 and 60'), findsOneWidget);
    expect(meRepo.captured, isNull); // save was blocked by validation
    expect(prefsRepo.captured, isNull);
  });

  testWidgets('clearing the expected CTC field sends an explicit null',
      (tester) async {
    final prefsRepo = _CapturingPrefsRepo(
      dto: const PreferencesDto(
        desiredRole: null,
        locations: ['Pune'],
        expectedCtc: '1200000.00',
      ),
    );
    await _pump(tester, meRepo: _CapturingMeRepo(), prefsRepo: prefsRepo);

    final ctcField = find.widgetWithText(TextFormField, 'Expected CTC (₹/yr)');
    await tester.scrollUntilVisible(
      ctcField,
      100,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      tester
          .widget<TextField>(
            find.descendant(of: ctcField, matching: find.byType(TextField)),
          )
          .controller!
          .text,
      '1200000.00', // seeded from the fetched preferences
    );
    await tester.enterText(ctcField, '');

    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(prefsRepo.captured, isNotNull);
    final json = prefsRepo.captured!.toJson();
    expect(json.containsKey('expected_ctc'), isTrue);
    expect(json['expected_ctc'], isNull); // explicit null actually clears
  });

  testWidgets(
      'partial failure (profile saved, preferences failed) says which half',
      (tester) async {
    final meRepo = _CapturingMeRepo();
    final prefsRepo = _CapturingPrefsRepo(failUpdate: true);
    await _pump(tester, meRepo: meRepo, prefsRepo: prefsRepo);

    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(meRepo.captured, isNotNull); // profile half went through
    expect(
      find.text("Saved your profile, but couldn't save preferences. "
          'Try again.'),
      findsOneWidget,
    );
  });

  testWidgets('form is unreachable while the preferences fetch is pending',
      (tester) async {
    await _pump(
      tester,
      meRepo: _CapturingMeRepo(),
      prefsRepo: _PendingPrefsRepo(),
      settle: false, // the spinner animates forever; pumpAndSettle would hang
    );
    await tester.pump();
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'Full name'), findsNothing);
    expect(find.text('Save'), findsNothing); // no save possible
  });
}
