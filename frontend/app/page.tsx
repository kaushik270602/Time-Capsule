import Link from 'next/link'

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 sm:p-8 bg-gradient-to-b from-stone-50 to-white">
      <div className="max-w-2xl text-center">
        <h1 className="text-4xl sm:text-5xl font-bold mb-4 text-amber-500">TimeLock</h1>
        <p className="text-lg sm:text-xl text-stone-600 mb-6 sm:mb-8">
          AI Powered Digital Time Capsule
        </p>
        <p className="text-stone-500 mb-10 sm:mb-12 max-w-lg mx-auto text-sm sm:text-base">
          Preserve your memories, predictions, and messages for the future.
          Lock them away until the perfect moment, then let AI help you reflect
          on how far you have come.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center mb-10 sm:mb-12">
          <Link
            href="/register"
            className="px-8 py-3 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 transition-colors"
          >
            Get Started
          </Link>
          <Link
            href="/login"
            className="px-8 py-3 border border-stone-300 text-stone-700 rounded-lg font-medium hover:bg-stone-50 transition-colors"
          >
            Sign In
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 text-left">
          <div className="p-5 sm:p-6 rounded-xl bg-white border border-stone-200 shadow-sm">
            <div className="text-2xl mb-2">🔒</div>
            <h3 className="font-semibold text-stone-900 mb-1">Time-Locked</h3>
            <p className="text-sm text-stone-500">
              Content stays sealed until your chosen unlock date.
            </p>
          </div>
          <div className="p-5 sm:p-6 rounded-xl bg-white border border-stone-200 shadow-sm">
            <div className="text-2xl mb-2">🤖</div>
            <h3 className="font-semibold text-stone-900 mb-1">AI Insights</h3>
            <p className="text-sm text-stone-500">
              Get summaries and reflections when your capsule opens.
            </p>
          </div>
          <div className="p-5 sm:p-6 rounded-xl bg-white border border-stone-200 shadow-sm">
            <div className="text-2xl mb-2">🌍</div>
            <h3 className="font-semibold text-stone-900 mb-1">Share Publicly</h3>
            <p className="text-sm text-stone-500">
              Make predictions visible to everyone after unlock.
            </p>
          </div>
        </div>

        <div className="mt-10 sm:mt-12">
          <Link
            href="/public"
            className="text-sm text-stone-400 hover:text-amber-600 transition-colors"
          >
            Browse public capsules →
          </Link>
        </div>
      </div>
    </main>
  )
}
