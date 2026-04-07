"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import FormInput from "@/components/ui/FormInput";

export default function RegisterForm() {
  const { register, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!email) errs.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      errs.email = "Enter a valid email address";
    if (!password) errs.password = "Password is required";
    else if (password.length < 8)
      errs.password = "Password must be at least 8 characters";
    else if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/\d/.test(password))
      errs.password = "Password must include uppercase, lowercase, and a number";
    if (password !== confirmPassword)
      errs.confirmPassword = "Passwords do not match";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      await register(email, password);
      // Auto-login after registration
      await login(email, password);
      router.push("/dashboard");
    } catch (err: any) {
      setErrors({ form: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <h2 className="text-2xl font-bold text-stone-900 text-center">Create your account</h2>
      {errors.form && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
          {errors.form}
        </div>
      )}
      <FormInput
        id="register-email"
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errors.email}
        autoComplete="email"
        required
      />
      <FormInput
        id="register-password"
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
        autoComplete="new-password"
        required
      />
      <FormInput
        id="register-confirm-password"
        label="Confirm Password"
        type="password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        error={errors.confirmPassword}
        autoComplete="new-password"
        required
      />
      <button
        type="submit"
        disabled={submitting}
        className="w-full py-2 px-4 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Creating account..." : "Create account"}
      </button>
      <p className="text-center text-sm text-stone-600">
        Already have an account?{" "}
        <Link href="/login" className="text-amber-600 hover:text-amber-500 font-medium">
          Sign in
        </Link>
      </p>
    </form>
  );
}
