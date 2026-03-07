import SwiftUI
import AuthenticationServices

struct AuthView: View {

    @EnvironmentObject var viewModel: AppViewModel
    @State private var email = ""
    @State private var password = ""
    @State private var isSigningIn = false

    var body: some View {
        ScrollView {
            VStack(spacing: 30) {

                Spacer()
                    .frame(height: 60)

                // Logo
                Image(systemName: "light.max")
                    .font(.system(size: 60))
                    .foregroundStyle(.blue.gradient)

                Text("Welcome Back")
                    .font(.title)
                    .fontWeight(.bold)

                // Sign in with Apple
                SignInWithAppleButton(
                    onRequest: { request in
                        request.requestedScopes = [.fullName, .email]
                    },
                    onCompletion: { result in
                        handleSignInWithApple(result)
                    }
                )
                .signInWithAppleButtonStyle(.black)
                .frame(height: 50)
                .padding(.horizontal, 30)

                // Divider
                HStack {
                    Rectangle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(height: 1)
                    Text("or")
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 12)
                    Rectangle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(height: 1)
                }
                .padding(.horizontal, 30)

                // Email/Password Form
                VStack(spacing: 16) {
                    TextField("Email", text: $email)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.emailAddress)
                        .autocapitalization(.none)
                        .keyboardType(.emailAddress)

                    SecureField("Password", text: $password)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.password)

                    Button(action: {
                        handleEmailPasswordSignIn()
                    }) {
                        HStack {
                            if isSigningIn {
                                ProgressView()
                                    .tint(.white)
                            }
                            Text(isSigningIn ? "Signing In..." : "Sign In")
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(12)
                    }
                    .disabled(isSigningIn || email.isEmpty || password.isEmpty)
                }
                .padding(.horizontal, 30)

                // Sign Up Link
                HStack {
                    Text("Don't have an account?")
                        .foregroundColor(.secondary)
                    Button("Sign Up") {
                        // Sign up action (mock)
                        print("Sign up tapped")
                    }
                    .foregroundColor(.blue)
                }
                .font(.subheadline)

                Spacer()
            }
        }
    }

    // MARK: - Actions

    private func handleEmailPasswordSignIn() {
        isSigningIn = true

        // Mock authentication - in production, this would call a real auth service
        Task {
            try? await Task.sleep(nanoseconds: 1_500_000_000) // 1.5 second delay
            viewModel.completeAuthentication()
            isSigningIn = false
        }
    }

    private func handleSignInWithApple(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .success:
            // Mock - in production, this would validate the credential
            viewModel.completeAuthentication()
        case .failure(let error):
            print("Sign in with Apple failed: \(error.localizedDescription)")
        }
    }
}

// MARK: - Preview

#Preview {
    AuthView()
        .environmentObject(AppViewModel())
}
