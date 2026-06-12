import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/presentation/profile/edit_profile_screen.dart';
import 'package:jobify_app/presentation/profile/me_controller.dart';

class _CapturingRepo implements MeRepository {
  ProfileUpdateDto? captured;
  @override
  Future<MeDto> fetch() async => const MeDto(
        id: 'u1',
        email: 'e@e.com',
        role: 'applicant',
        applicant: ApplicantSummaryDto(
          id: 'a1',
          fullName: 'Alice',
          locations: ['Pune'],
        ),
      );
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async {
    captured = update;
    return fetch();
  }
}

void main() {
  testWidgets('renders seeded values, adds a chip, saves', (tester) async {
    final repo = _CapturingRepo();
    final container = ProviderContainer(
      overrides: [meRepositoryProvider.overrideWithValue(repo)],
    );
    addTearDown(container.dispose);
    await container.read(meControllerProvider.future); // warm the me cache

    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const EditProfileScreen()),
      ],
    );

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

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

    expect(repo.captured, isNotNull);
    expect(repo.captured!.fullName, 'Alice');
    expect(repo.captured!.locations, ['Pune', 'Mumbai']);
  });

  testWidgets('out-of-range experience blocks save', (tester) async {
    final repo = _CapturingRepo();
    final container = ProviderContainer(
      overrides: [meRepositoryProvider.overrideWithValue(repo)],
    );
    addTearDown(container.dispose);
    await container.read(meControllerProvider.future);

    final router = GoRouter(
      routes: [
        GoRoute(path: '/', builder: (_, __) => const EditProfileScreen()),
      ],
    );
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Years of experience'),
      '99', // exceeds max 60
    );
    await tester.tap(find.widgetWithText(TextButton, 'Save'));
    await tester.pumpAndSettle();

    expect(find.text('Must be between 0 and 60'), findsOneWidget);
    expect(repo.captured, isNull); // save was blocked by validation
  });
}
