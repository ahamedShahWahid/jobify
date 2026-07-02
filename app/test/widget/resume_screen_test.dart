import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/data/resume/resume_parse_status.dart';
import 'package:jobify_app/data/resume/resume_repository.dart';
import 'package:jobify_app/data/resume/resume_repository_impl.dart';
import 'package:jobify_app/presentation/preferences/preferences_screen.dart';
import 'package:jobify_app/presentation/resume/resume_screen.dart';

class _Repo implements ResumeRepository {
  _Repo(this._current);
  final ResumeDto? _current;

  @override
  Future<ResumeDto?> current() async => _current;

  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async =>
      throw UnimplementedError();
}

class _IncompletePrefsRepo implements PreferencesRepository {
  @override
  Future<PreferencesDto> fetch() async =>
      const PreferencesDto(desiredRole: null, locations: [], expectedCtc: null);
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async => fetch();
}

ResumeDto _dto(ResumeParseStatus s) => ResumeDto(
      id: 'r1',
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: s,
      createdAt: DateTime(2026),
    );

Future<void> _pump(WidgetTester tester, ResumeDto? current) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [resumeRepositoryProvider.overrideWithValue(_Repo(current))],
      child: const MaterialApp(home: ResumeScreen()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('empty state shows prompt + upload button', (tester) async {
    await _pump(tester, null);
    expect(find.textContaining('No r\xe9sum\xe9 yet'), findsOneWidget);
    expect(find.text('Upload / Replace r\xe9sum\xe9'), findsOneWidget);
  });

  testWidgets('parsed resume shows filename + Ready chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.parsed));
    expect(find.text('cv.pdf'), findsOneWidget);
    expect(find.text('Ready'), findsOneWidget);
  });

  testWidgets('failed resume shows error chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.failed));
    expect(find.text("Couldn't parse — try again"), findsOneWidget);
  });

  testWidgets('parsing resume shows processing chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.parsing));
    expect(find.text('Processing…'), findsOneWidget);
  });

  testWidgets('navigates to preferences after parse settles when incomplete',
      (tester) async {
    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const ResumeScreen()),
        GoRoute(
          path: '/profile/preferences',
          builder: (_, s) => PreferencesScreen(resume: s.extra as ResumeDto?),
        ),
      ],
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          resumeRepositoryProvider
              .overrideWithValue(_Repo(_dto(ResumeParseStatus.parsed))),
          preferencesRepositoryProvider
              .overrideWithValue(_IncompletePrefsRepo()),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final state = tester.state<State<ResumeScreen>>(find.byType(ResumeScreen));
    // `_maybeNavigateToPreferences` is private to resume_screen.dart's
    // library, so it can't be invoked via `(state as dynamic)` from this
    // test file (Dart privacy is per-library, not per-file-with-underscore
    // — dynamic dispatch of a `_foo` symbol from another library always
    // throws NoSuchMethodError). `maybeNavigateToPreferencesForTest` is a
    // public @visibleForTesting forwarder added for exactly this purpose.
    final navigate =
        (state as dynamic).maybeNavigateToPreferencesForTest() as Future<void>;
    await navigate;
    await tester.pumpAndSettle();

    expect(find.byType(PreferencesScreen), findsOneWidget);
  });
}
