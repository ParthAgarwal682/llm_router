'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/chat');
  }, [router]);

  return (
    <div className="h-screen w-screen bg-zinc-950 flex items-center justify-center text-zinc-400 text-xs">
      Redirecting to chat workspace...
    </div>
  );
}
