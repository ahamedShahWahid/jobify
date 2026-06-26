import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/auth/google_web_sign_in.dart';
import 'package:jobify_app/presentation/auth/delete_success_snackbar_provider.dart';
import 'package:jobify_app/presentation/auth/sign_in_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/arrive.dart';

class SignInScreen extends ConsumerWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // One-time snackbar after account deletion.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (ref.read(deleteSuccessSnackbarProvider)) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Your account has been deleted.')),
        );
        ref.read(deleteSuccessSnackbarProvider.notifier).consume();
      }
    });

    ref.listen<AsyncValue<void>>(signInControllerProvider, (_, next) {
      next.whenOrNull(
        error: (e, _) {
          final msg = switch (e) {
            AuthException(:final slug)
                when slug == 'google_sign_in_cancelled' =>
              null,
            NetworkException _ =>
              "Couldn't reach Jobify. Check your connection.",
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
          padding: const EdgeInsets.symmetric(horizontal: JobifySpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Arrive(
                index: 0,
                child: Text(
                  'Jobify',
                  style: theme.textTheme.displayLarge?.copyWith(
                    color: theme.brightness == Brightness.dark
                        ? JobifyColors.brandBlueDark
                        : JobifyColors.brandBlueLight,
                  ),
                ),
              ),
              const SizedBox(height: JobifySpacing.sm),
              Arrive(
                index: 1,
                child: Text(
                  'Roles that match you, not the other way around.',
                  style: theme.textTheme.bodyLarge
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              ),
              const SizedBox(height: JobifySpacing.xxl),
              // Web authenticates via Google's rendered button (the only web
              // path that yields an ID token); mobile uses the imperative flow.
              Arrive(
                index: 2,
                child: kIsWeb
                    ? _WebSignInButton(isLoading: isLoading)
                    : OutlinedButton.icon(
                        icon: isLoading
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.login),
                        label: Text(
                          isLoading ? 'Signing in…' : 'Continue with Google',
                        ),
                        onPressed: isLoading
                            ? null
                            : () => ref
                                .read(signInControllerProvider.notifier)
                                .signInWithGoogle(),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Web sign-in affordance: shows Google's rendered button once the GIS client
/// is initialized, a spinner while initializing or while the backend exchange
/// is in flight, and a fallback message if init failed.
class _WebSignInButton extends ConsumerWidget {
  const _WebSignInButton({required this.isLoading});

  final bool isLoading;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (isLoading) {
      return const SizedBox(
        width: 24,
        height: 24,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    return ref.watch(googleWebSignInProvider).when(
          data: (google) => google.button(),
          loading: () => const SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          error: (_, __) => Text(
            "Couldn't load Google sign-in. Refresh and try again.",
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
        );
  }
}
