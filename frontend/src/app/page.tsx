export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-bold mb-4">FIOS</h1>
      <p className="text-lg text-gray-600">
        Financial Intelligence Operating System
      </p>
      <a
        href="/health"
        className="mt-8 text-blue-600 hover:text-blue-800 underline"
      >
        System Health
      </a>
    </main>
  );
}
