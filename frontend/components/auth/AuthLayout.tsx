"use client";

import React from "react";
import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-stone-50 px-4">
      <div className="mb-8">
        <Link href="/" className="text-3xl font-bold text-amber-500">
          TimeLock
        </Link>
      </div>
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm border border-stone-200 p-8">
        {children}
      </div>
    </div>
  );
}
