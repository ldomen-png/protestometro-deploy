import { Suspense } from "react";
import { Metadata } from "next";
import { auth } from "@/auth";
import { Navbar } from "@/components/navbar";
import { ResultRow } from "@/components/result-row";
import { FilterSidebar } from "@/components/filter-sidebar";
import { FilterSheet } from "@/components/filter-sheet";
import { ActiveFilterChips } from "@/components/active-filter-chips";
import { AlertBanner } from "@/components/alert-banner";
import { ExportCsvButton } from "@/components/export-csv-button";
import { ShareSearchButton } from "@/components/share-search-button";
import { Pagination } from "@/components/pagination";
import { TrackEvent } from "@/components/track-event";
import { searchTenders, getFilterCounts } from "@/lib/queries";

export const metadata: Metadata = {
  title: "Busca Licitaciones del Gobierno Mexicano | El Jale",
  description: "Busca y filtra 370,000+ licitaciones de gobierno federal, estatal y municipal. Crea alertas automáticas, exporta resultados y gana contratos.",
  openGraph: {
    title: "Busca Licitaciones del Gobierno Mexicano",
    description: "Acceso directo a todas las licitaciones gubernamentales de México",
    type: "website",
    url: "https://eljale.mx/busqueda",
  },
};

export default async function BusquedaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await auth();
  const isLoggedIn = !!session?.user;

  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q : "";
  // Support both single and multi-value params
  const stateParam = params.estado;
  const states = Array.isArray(stateParam) ? stateParam : (stateParam ? [stateParam] : []);
  const statusParam = params.estatus;
  const statuses = Array.isArray(statusParam) ? statusParam : (statusParam ? [statusParam] : []);
  const procedureParam = params.procedimiento;
  const procedures = Array.isArray(procedureParam) ? procedureParam : (procedureParam ? [procedureParam] : []);
  const levelParam = params.nivel;
  const levels = Array.isArray(levelParam) ? levelParam : (levelParam ? [levelParam] : []);
  const categoriaParam = params.categoria;
  const categorias = Array.isArray(categoriaParam) ? categoriaParam : (categoriaParam ? [categoriaParam] : []);
  const page = parseInt(typeof params.pagina === "string" ? params.pagina : "1") || 1;
  const perPage = 20;

  const filters: Record<string, unknown> = {
    limit: perPage,
    offset: (page - 1) * perPage,
  };
  if (states.length) filters.states = states;
  if (statuses.length) filters.status = statuses;
  if (procedures.length) filters.procedure_type = procedures;
  if (levels.length) filters.levels = levels;
  if (categorias.length) filters.category = categorias;

  const { tenders, total, isCapped, allMatchedIds } = await searchTenders(q, filters as Parameters<typeof searchTenders>[1]);
  const totalPages = Math.ceil(total / perPage);
  const hasSemantic = q.trim().length > 0;

  // Facet counts from the filtered result set (consistent with displayed results)
  const filterCounts = hasSemantic && allMatchedIds && allMatchedIds.length > 0
    ? await getFilterCounts(allMatchedIds)
    : null;

  function buildUrl(overrides: Record<string, string>): string {
    const sp = new URLSearchParams();
    if (q) sp.set("q", q);
    for (const s of states) sp.append("estado", s);
    for (const s of statuses) sp.append("estatus", s);
    for (const p of procedures) sp.append("procedimiento", p);
    for (const l of levels) sp.append("nivel", l);
    for (const c of categorias) sp.append("categoria", c);
    sp.set("pagina", String(page));
    for (const [k, v] of Object.entries(overrides)) sp.set(k, v);
    if (sp.get("pagina") === "1") sp.delete("pagina");
    return `/busqueda?${sp.toString()}`;
  }

  return (
    <>
      <Navbar />

      <div className="mx-auto max-w-[1280px] px-4 py-6">
        {/* Search bar — sticky below nav */}
        <div className="sticky top-[56px] z-40 -mx-4 border-b border-gray-100 bg-white px-4 pb-3 pt-2 lg:border-b-0">
          <form method="GET" action="/busqueda">
            <div className="flex items-center gap-2">
              <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--ink)] bg-white px-4 py-2.5 focus-within:shadow-[0_0_0_3px_rgba(0,0,0,0.08)]">
                <svg className="h-5 w-5 text-[var(--ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  name="q"
                  type="text"
                  defaultValue={q}
                  placeholder="Busca: 'paneles solares', 'servicios de limpieza', 'software'…"
                  className="flex-1 border-0 bg-transparent text-sm text-[var(--ink)] placeholder-[var(--ink-muted)] outline-none"
                />
              </div>
              <button
                type="submit"
                className="hidden shrink-0 rounded-lg bg-[#111] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#333] lg:block"
              >
                Buscar
              </button>
              {/* Mobile filter trigger */}
              <Suspense>
                <FilterSheet counts={filterCounts} />
              </Suspense>
            </div>
          </form>
        </div>

        {hasSemantic && <TrackEvent event="search" properties={{ query: q, results: total }} />}

        {/* Active filter chips */}
        <Suspense>
          <ActiveFilterChips />
        </Suspense>

        {/* Alert banner */}
        {hasSemantic && total > 0 && (
          <AlertBanner query={q} total={total} />
        )}

        <div className="flex gap-6">
          {/* Filter sidebar */}
          <Suspense>
            <FilterSidebar counts={filterCounts} />
          </Suspense>

          {/* Results */}
          <main className="min-w-0 flex-1">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm text-[var(--ink-muted)]">
                <span className="font-mono">{total.toLocaleString("es-MX")}{isCapped ? "+" : ""}</span> resultado{total !== 1 ? "s" : ""}
                {q && (
                  <span> para &ldquo;<span className="font-medium text-[var(--ink)]">{q}</span>&rdquo;</span>
                )}
              </p>
              {total > 0 && (
                <div className="flex items-center gap-2">
                  {hasSemantic && (
                    <Suspense>
                      <ShareSearchButton query={q} total={total} />
                    </Suspense>
                  )}
                  <Suspense>
                    <ExportCsvButton />
                  </Suspense>
                </div>
              )}
            </div>

            {tenders.length === 0 ? (
              <div className="rounded-lg border border-[var(--border)] bg-white px-6 py-16 text-center">
                {!hasSemantic ? (
                  <>
                    <h2 className="text-lg font-semibold text-[var(--ink)]">Bienvenido a El Jale</h2>
                    <p className="mt-2 text-[var(--ink-soft)]">
                      Acceso directo a 370,000+ licitaciones del gobierno mexicano.
                    </p>
                    <p className="mt-3 text-sm text-[var(--ink-muted)]">
                      Busca productos o servicios que vendes, filtra por estado, categoría y procedimiento, 
                      y crea alertas automáticas para no perder oportunidades.
                    </p>
                    <div className="mt-4 flex items-center justify-center gap-3">
                      <a 
                        href="/registro" 
                        className="rounded-lg bg-[#111] px-4 py-2 text-sm font-medium text-white hover:bg-[#333]"
                      >
                        Crear cuenta gratis
                      </a>
                      <a 
                        href="/?q=paneles+solares" 
                        className="rounded-lg border border-[var(--ink)] px-4 py-2 text-sm font-medium text-[var(--ink)] hover:bg-[var(--surface)]"
                      >
                        Ver ejemplo
                      </a>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-[var(--ink-soft)]">No se encontraron licitaciones.</p>
                    <p className="mt-1 text-sm text-[var(--ink-muted)]">Intenta con otros términos o filtros.</p>
                    <div className="mt-4">
                      <a 
                        href="/busqueda" 
                        className="inline-block rounded-lg bg-[#111] px-4 py-2 text-sm font-medium text-white hover:bg-[#333]"
                      >
                        Limpiar búsqueda
                      </a>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <>
                {/* Table header */}
                <div className="hidden md:grid grid-cols-[1fr_180px_110px_110px_80px_36px] items-center gap-2 border-b border-[var(--ink)] bg-[var(--surface)] px-4 py-2.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--ink)]">Licitación</span>
                  <span className="hidden text-[11px] font-semibold uppercase tracking-wider text-[var(--ink)] md:block">Dependencia</span>
                  <span className="hidden text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--ink)] lg:block">Cierre</span>
                  <span className="text-center text-[11px] font-semibold uppercase tracking-wider text-[var(--ink)]">Estatus</span>
                  {hasSemantic && (
                    <span className="text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--ink)]">Match</span>
                  )}
                  <span />
                </div>

                {/* Rows */}
                <div className="flex flex-col gap-3 md:gap-0 md:bg-white">
                  {tenders.map((tender) => (
                    <ResultRow key={tender.id} tender={tender} showMatch={hasSemantic} isLoggedIn={isLoggedIn} />
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    total={total}
                    perPage={perPage}
                    buildUrl={(p) => buildUrl({ pagina: String(p) })}
                  />
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </>
  );
}
