import type { ReactNode } from 'react'
import { Card, PageHeader } from '../components/ui'

function Topic({ title, children }: { title: string; children: ReactNode }) {
  return <Card title={title}><div className="space-y-2 text-sm leading-relaxed text-slate-600">{children}</div></Card>
}

export default function AboutPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="About and Technical Details" subtitle="Beginner-friendly explanations of the concepts behind CAIF, and of how this prototype differs from the research implementation." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Topic title="The research paper">
          <p>Reddy, Singh, Perais, Ros and Jimborean (CGO 2026) observe that cheap, non-speculative fusion hardware only fuses <b>adjacent</b> memory instructions, while hardware that fuses distant pairs (Helios) needs predictors, history buffers, validation and recovery. They move the work into LLVM: a middle-end pass reorders fusible pairs so they become consecutive, and back-end mechanisms keep them together.</p>
          <p>They evaluated neural-network layers and SPEC CPU 2017 on a simulated RISC-V core. In their results, simple consecutive-only hardware plus CAIF beat speculative Helios hardware with a normal compiler on the NN kernels.</p>
        </Topic>
        <Topic title="CAIF in one paragraph">
          <p>For every load (or store) <b>HEAD</b> in a basic block, scan forward for a <b>TAIL</b> of the same kind that touches the same 64-byte region. The instructions between them are the <b>catalyst</b>. Collect the TAIL's <b>use-def chain</b>, i.e. the catalyst instructions that compute its address or stored value. If the chain contains the HEAD, give up. Otherwise use alias analysis to check that neither the TAIL nor its chain conflicts with memory accesses they would jump over. If everything is safe, hoist the chain above the HEAD and place the TAIL right after it.</p>
        </Topic>
        <Topic title="LLVM">
          <p>LLVM is a compiler framework. Front ends (clang, MLIR) turn source code into <b>LLVM IR</b>, a typed, SSA-form intermediate representation. Optimisation passes (<code>opt</code>) transform the IR, and the back end (<code>llc</code>) turns it into machine code. CAIF adds passes in both the middle end (reordering, using alias analysis, SCEV and use-def chains) and the back end.</p>
        </Topic>
        <Topic title="Instruction scheduling">
          <p>Scheduling chooses the order of instructions without changing what the program computes. Any order is legal as long as every dependence is respected. Normal schedulers aim to hide latency. CAIF's ordering instead aims to make fusible pairs adjacent.</p>
        </Topic>
        <Topic title="Dependency analysis">
          <p><b>RAW</b> (true): B reads what A wrote. <b>WAR</b> (anti): B overwrites something A still has to read. <b>WAW</b> (output): both write the same place and the last write must stay last. These apply to registers and to memory.</p>
          <p>LLVM IR is in SSA form, so register WAR/WAW cannot occur there. Our register-level teaching ISA is not SSA, so this prototype also checks them.</p>
        </Topic>
        <Topic title="Alias analysis">
          <p>Two memory accesses <i>alias</i> if they may touch the same bytes. The analysis answers NO / MUST / PARTIAL / MAY alias. Here, distinct symbols never alias, accesses from the same base are compared by byte ranges, and unknown pointers are conservatively MAY-alias. A transformation is allowed only if it does not reorder a store with any access that may alias it.</p>
          <p>The paper combines LLVM's built-in analyses with SVF's Andersen and flow-sensitive analyses, plus GraphAA for interprocedural cases.</p>
        </Topic>
        <Topic title="Use-def chains">
          <p>For each use of a value, the use-def chain lists the instruction that defined it, and transitively that instruction's own inputs. CAIF uses the TAIL's chain to know exactly which catalyst instructions must move up with the TAIL. In SSA IR the chain is explicit. Here it is rebuilt with a reaching-definitions scan inside the basic block.</p>
        </Topic>
        <Topic title="SelectionDAG, pseudo-instructions and DAG mutations">
          <p>In LLVM's back end, each basic block becomes a <b>SelectionDAG</b>: a graph of operations and dependences used for instruction selection and scheduling. The scheduler may undo the middle end's order.</p>
          <p>The paper therefore (1) packs each fusible pair into a <b>pseudo-instruction</b> before scheduling and register allocation and expands it afterwards, and (2) adds weak cluster edges through <b>DAG mutations</b> (based on <code>BaseMemOpClusterMutation</code>) for pairs that appear later, such as stack spills. This prototype has no back end, so these mechanisms are explained but not re-implemented.</p>
        </Topic>
        <Topic title="Implementation limitations">
          <ul className="list-disc space-y-1 pl-5">
            <li>Simulated ISA (not RISC-V). No real hardware or cycle-level simulation, so no speedup is claimed.</li>
            <li>Alias analysis is symbolic and intra-block. Indexed addressing (<code>a[b[i]]</code>) is treated as an unknown pointer.</li>
            <li>The 64-byte condition is modelled as "both accesses fit in a 64-byte span", without knowing cache-line alignment.</li>
            <li>No loop unrolling (the paper uses dynamic unrolling by 2), no register-pressure model and no back end.</li>
            <li>Safety rests on the dependence and alias analysis. The validator re-checks every result with a commutation test (which shares the alias analysis) and with interpreter-based differential testing (which does not). This is testing evidence, not a formal proof.</li>
            <li>Alias analysis assumes objects of at most 16 MiB placed apart, and treats huge offsets (possible 64-bit wrap-around) and out-of-bounds accesses as may-alias.</li>
          </ul>
        </Topic>
        <Topic title="Research paper vs this prototype">
          <table className="tbl">
            <thead><tr><th>Aspect</th><th>Paper</th><th>Prototype</th></tr></thead>
            <tbody>
              <tr><td>Input</td><td>LLVM IR from C/C++ and ONNX models</td><td>teaching assembly</td></tr>
              <tr><td>Distance</td><td>stripAndAccumulate / SCEV</td><td>symbolic base + constant offset</td></tr>
              <tr><td>Aliasing</td><td>LLVM AA + SVF + GraphAA</td><td>conservative symbolic AA</td></tr>
              <tr><td>Order kept by</td><td>pseudo-instr. + DAGMutation</td><td>n/a (no back end)</td></tr>
              <tr><td>Evaluation</td><td>Spike + cycle simulator</td><td>opportunity counts + validation</td></tr>
            </tbody>
          </table>
        </Topic>
      </div>
    </div>
  )
}
