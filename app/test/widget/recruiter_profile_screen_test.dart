import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/me/me_dto.dart';
import 'package:jobify_app/data/me/me_repository.dart';
import 'package:jobify_app/data/me/me_repository_impl.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/presentation/recruiter/recruiter_profile_screen.dart';

class _FakeMeRepo implements MeRepository {
  @override
  Future<MeDto> fetch() async => const MeDto(
        id: 'u1',
        email: 'recruiter@acme.com',
        role: 'recruiter',
      );

  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async =>
      throw UnimplementedError();
}

void main() {
  testWidgets('shows email and a Sign out button', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          meRepositoryProvider.overrideWithValue(_FakeMeRepo()),
        ],
        child: MaterialApp(
          theme: ThemeData.light(useMaterial3: true),
          home: const RecruiterProfileScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('recruiter@acme.com'), findsWidgets);
    expect(find.widgetWithText(OutlinedButton, 'Sign out'), findsOneWidget);
    expect(find.text('Privacy & data'), findsOneWidget);
  });
}
