import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/presentation/auth/sign_in_controller.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';

class SignInScreen extends ConsumerWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen<AsyncValue<void>>(signInControllerProvider, (_, next) {
      next.whenOrNull(
        error: (e, _) {
          final msg = switch (e) {
            AuthException(:final slug)
                when slug == 'google_sign_in_cancelled' =>
              null,
            NetworkException _ =>
              "Couldn't reach KPA. Check your connection.",
            AuthException(:final detail) =>
              detail ?? 'Sign-in failed. Try again.',
            _ => 'Sign-in failed. Try again.',
          };
          if (msg != null) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(msg)),
            );
          }
        },
      );
    });

    final state = ref.watch(signInControllerProvider);
    final isLoading = state.isLoading;
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: KpaSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('KPA', style: theme.textTheme.displayMedium),
              const SizedBox(height: KpaSpacing.sm),
              Text(
                'Roles that match you, not the other way around.',
                style: theme.textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: KpaSpacing.xxl),
              FilledButton.icon(
                icon: isLoading
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child:
                            CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.login),
                label: Text(isLoading ? 'Signing in…' : 'Continue with Google'),
                onPressed: isLoading
                    ? null
                    : () => ref
                        .read(signInControllerProvider.notifier)
                        .signInWithGoogle(),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
